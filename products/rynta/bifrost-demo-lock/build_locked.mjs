// 잠금판 코드 컴포넌트 생성: 화면 HTML을 gzip 뒤 AES-256-GCM으로 암호화해 TSX에 담음.
// 사용: node build_locked.mjs <화면 HTML> <출력 TSX> <비밀번호 파일>
// 비밀번호 파일이 없으면 새로 만들고(Crockford base32 12자), 있으면 그 비밀번호를 씀.
import { readFileSync, writeFileSync, existsSync, chmodSync } from "node:fs"
import { gzipSync, gunzipSync } from "node:zlib"
import { webcrypto as wc, randomBytes } from "node:crypto"

const [HTML_PATH, OUT, SECRET] = process.argv.slice(2)
const ITER = 600000
const A = "0123456789ABCDEFGHJKMNPQRSTVWXYZ"
const norm = p => p.toUpperCase().replace(/[\s-]/g, "").replace(/O/g, "0").replace(/[IL]/g, "1")

let pw
if (existsSync(SECRET)) pw = readFileSync(SECRET, "utf8").trim()
else {
  const r = randomBytes(12)
  const c = [...r].map(b => A[b & 31]).join("")
  pw = `${c.slice(0, 4)}-${c.slice(4, 8)}-${c.slice(8, 12)}`
  writeFileSync(SECRET, pw + "\n")
  chmodSync(SECRET, 0o600)
}

const html = readFileSync(HTML_PATH)
const zipped = gzipSync(html, { level: 9 })
const salt = randomBytes(16), iv = randomBytes(12)
const base = await wc.subtle.importKey("raw", new TextEncoder().encode(norm(pw)), "PBKDF2", false, ["deriveKey"])
const key = await wc.subtle.deriveKey({ name: "PBKDF2", salt, iterations: ITER, hash: "SHA-256" }, base, { name: "AES-GCM", length: 256 }, false, ["encrypt", "decrypt"])
const ct = Buffer.from(await wc.subtle.encrypt({ name: "AES-GCM", iv }, key, zipped))

// 자체 점검: 같은 키로 풀어 원문과 바이트 대조
const back = gunzipSync(Buffer.from(await wc.subtle.decrypt({ name: "AES-GCM", iv }, key, ct)))
if (!back.equals(html)) throw new Error("복호화 결과가 원문과 다름")

const b64 = ct.toString("base64")
const lines = []
for (let i = 0; i < b64.length; i += 1000) lines.push(JSON.stringify(b64.slice(i, i + 1000)))

const tsx = `// RYNTA Bifrost 적용 전후 화면 v0.8.1 잠금판: rynta.io/bifrost/demo 페이지용 코드 컴포넌트
// 화면 HTML을 gzip으로 줄인 뒤 AES-256-GCM으로 암호화해 담음. 키는 비밀번호에서 PBKDF2-SHA256 ${ITER.toLocaleString("en-US")}회로 만듦.
// 비밀번호를 넣으면 브라우저 안에서만 풀어 iframe으로 표시. 비밀번호 없이는 페이지 소스로도 화면 내용을 볼 수 없음.
// 화면의 모든 수치는 합성 데이터. 페이지에는 이 컴포넌트 하나만 두고 너비 Fill(100%), 높이 100vh로 배치.
import * as React from "react"

const C = { bg: "#F3F5F7", surface: "#FEFEFD", line: "#D5DDE4", ink: "#1F2B36", ink2: "#495769", steel: "#406890", mark: "#4B6C79", danger: "#A34A3F" }
const FONT = '"Pretendard", -apple-system, BlinkMacSystemFont, "Apple SD Gothic Neo", "Noto Sans KR", "Malgun Gothic", sans-serif'

function bytes(b64: string): Uint8Array {
    const s = atob(b64)
    const out = new Uint8Array(s.length)
    for (let i = 0; i < s.length; i++) out[i] = s.charCodeAt(i)
    return out
}

// 대소문자, 공백, 하이픈 차이는 무시하고 O는 0, I·L은 1로 읽음
const norm = (p: string) => p.toUpperCase().replace(/[\\s-]/g, "").replace(/O/g, "0").replace(/[IL]/g, "1")

async function unlock(password: string): Promise<string> {
    const base = await crypto.subtle.importKey("raw", new TextEncoder().encode(norm(password)), "PBKDF2", false, ["deriveKey"])
    const key = await crypto.subtle.deriveKey(
        { name: "PBKDF2", salt: bytes(SALT), iterations: ITER, hash: "SHA-256" },
        base,
        { name: "AES-GCM", length: 256 },
        false,
        ["decrypt"]
    )
    const zipped = await crypto.subtle.decrypt({ name: "AES-GCM", iv: bytes(IV) }, key, bytes(DATA.join("")))
    const stream = new Blob([zipped]).stream().pipeThrough(new DecompressionStream("gzip"))
    return new Response(stream).text()
}

/**
 * @framerIntrinsicWidth 1600
 * @framerIntrinsicHeight 900
 * @framerSupportedLayoutWidth any-prefer-fixed
 * @framerSupportedLayoutHeight any-prefer-fixed
 */
export default function BifrostScreenLocked(props: { style?: React.CSSProperties }) {
    const [doc, setDoc] = React.useState<string | null>(null)
    const [pw, setPw] = React.useState("")
    const [busy, setBusy] = React.useState(false)
    const [err, setErr] = React.useState("")

    async function submit(e: React.FormEvent) {
        e.preventDefault()
        if (!pw.trim() || busy) return
        if (typeof DecompressionStream === "undefined" || !globalThis.crypto?.subtle) {
            setErr("이 브라우저에서는 열 수 없습니다. 최신 Chrome, Edge, Safari로 열어 주세요.")
            return
        }
        setBusy(true)
        setErr("")
        try {
            setDoc(await unlock(pw))
        } catch {
            setErr("비밀번호가 맞지 않습니다.")
        } finally {
            setBusy(false)
        }
    }

    const box: React.CSSProperties = { ...props.style, width: "100%", height: "100%", background: C.bg, overflow: "hidden" }
    if (doc)
        return (
            <div style={box}>
                <iframe srcDoc={doc} title="RYNTA Bifrost 적용 전후 비교" style={{ width: "100%", height: "100%", border: 0, display: "block" }} />
            </div>
        )
    return (
        <div style={{ ...box, display: "grid", placeItems: "center", padding: 16, boxSizing: "border-box", overflow: "auto", fontFamily: FONT }}>
            <form
                onSubmit={submit}
                style={{ width: "100%", maxWidth: 400, boxSizing: "border-box", display: "grid", gap: 16, padding: 28, background: C.surface, border: \`1px solid \${C.line}\`, borderRadius: 12 }}
            >
                <div style={{ display: "flex", alignItems: "center", gap: 10, color: C.mark }}>
                    <svg viewBox="17 18 54 40" width="34" height="26" aria-hidden="true">
                        <g fill="none" stroke="currentColor" strokeWidth="2.6">
                            <circle cx="26" cy="24" r="4" />
                            <circle cx="62" cy="24" r="4" />
                            <path d="M26 28V56M62 28V56M34 42.8V56M44 45.7V56M54 42.8V56M26 33.7C34 49.7 54 49.7 62 33.7" />
                            <path d="M18.7 56H69.3" strokeWidth="2.4" />
                        </g>
                    </svg>
                    <span style={{ color: C.ink, fontSize: 18, fontWeight: 700 }}>RYNTA Bifrost</span>
                </div>
                <div style={{ display: "grid", gap: 6 }}>
                    <div style={{ color: C.ink, fontSize: 16, fontWeight: 600 }}>적용 전후 비교</div>
                    <div style={{ color: C.ink2, fontSize: 14, lineHeight: 1.6 }}>안내받은 비밀번호를 입력하면 화면이 열립니다.</div>
                </div>
                <label style={{ display: "grid", gap: 6, color: C.ink2, fontSize: 13 }}>
                    비밀번호
                    <input
                        type="password"
                        value={pw}
                        onChange={(e) => setPw(e.target.value)}
                        autoComplete="off"
                        autoFocus
                        style={{ font: \`15px \${FONT}\`, padding: "10px 12px", color: C.ink, background: "#FFFFFF", border: \`1px solid \${C.line}\`, borderRadius: 8 }}
                    />
                </label>
                {err && (
                    <div role="alert" style={{ color: C.danger, fontSize: 13 }}>
                        {err}
                    </div>
                )}
                <button
                    type="submit"
                    disabled={busy}
                    style={{ font: \`600 15px \${FONT}\`, padding: "11px 0", color: "#FFFFFF", background: C.steel, border: 0, borderRadius: 8, cursor: busy ? "default" : "pointer", opacity: busy ? 0.7 : 1 }}
                >
                    {busy ? "여는 중" : "열기"}
                </button>
                <div style={{ color: C.ink2, fontSize: 12 }}>가상 환경 · 합성 데이터</div>
            </form>
        </div>
    )
}

const ITER = ${ITER}
const SALT = "${salt.toString("base64")}"
const IV = "${iv.toString("base64")}"

// 아래는 암호화한 화면 (gzip 뒤 AES-256-GCM, base64, 1,000자 단위로 분할)
const DATA: string[] = [
${lines.join(",\n")}
]
`
writeFileSync(OUT, tsx)
console.log(JSON.stringify({ html: html.length, gzip: zipped.length, cipher: ct.length, tsx: Buffer.byteLength(tsx), lines: lines.length }))

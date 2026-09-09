"""공개 배포용 영문 빌드 변환기.

화면 문자열은 런타임 i18n 이 옮기지만 원장 값(상태 코드·라벨·서식 항목명·서술문)은
원문 그대로 실린다. 공개 홈페이지에 올리는 영문 빌드는 그 값까지 영어여야 하므로
payload 를 만든 뒤 여기서 한 번 더 옮긴다. 사전은 세 층이다.

  1. risk_lib/ui_studio/data/en_dictionary.json  손으로 적은 원장 값·용어 사전 (우선)
  2. 화면 i18n (i18n.ko_to_en)                     화면 문자열과 겹치는 값
  3. 카탈로그                                        표·컬럼 한국어 라벨 → 물리 이름을 풀어 쓴 것

문자열 전체가 사전에 없으면 구분 기호(· , ( ) / 등)로 쪼개고, 띄어쓰기 단위로
가장 긴 구절부터 맞춰 옮긴다. 숫자+단위(건·종·행 …)는 규칙으로 옮긴다. 남는 한글은
MISSES 에 세어 두어 사전을 늘릴 근거가 된다. 공개 빌드는 SHA-256 지문도 지운다.
"""
from __future__ import annotations

import json
import re
from collections import Counter
from pathlib import Path

from risk_lib.datamodel import catalog as cat
from risk_lib.ui_studio import i18n as _i18n

DICT_PATH = Path(__file__).parent / "data" / "en_dictionary.json"
SENT_PATH = Path(__file__).parent / "data" / "en_sentences.json"     # 문장 통째 (정확히 일치)
FAM_PATH = Path(__file__).parent / "data" / "en_families.json"       # 숫자를 # 으로 바꾼 틀
UI_KEYS_PATH = Path(__file__).parent / "data" / "en_ui_keys.json"    # 화면 안에서 조합되는 UI 문자열 (원장 값 아님)
_JS_LIT = (re.compile(r"'((?:[^'\\\n]|\\.)*[가-힣](?:[^'\\\n]|\\.)*)'"),
           re.compile(r'"((?:[^"\\\n]|\\.)*[가-힣](?:[^"\\\n]|\\.)*)"'))
_NUMTOK = re.compile(r"[\d][\d,.\-%]*")
HANGUL = re.compile(r"[가-힣]")
_SPLIT = re.compile(r"([·,;:()\[\]{}/+×→←↔≥≤=<>|~%&\"'*#@!?…、。_\n\t]+|\s*[-]\s+|\s+[-]\s*|(?<=[가-힣])-|-(?=[가-힣]))")
_UNIT = re.compile(r"^([\d,.]+)(건|종|장|행|열|칸|쌍|구간|개|명|년|월|일|개월|분기|회|차|호|단계|등급|층|곳|배|인|개사|개국|좌|매|점|원|억원|억|조원|조|만원|만|천만원|천만|천원|천|백만원|백만|십억원|십억)$")
_UNIT_EN = {"건": "", "종": " types", "장": " tables", "행": " rows", "열": " columns", "칸": " cells", "쌍": " pairs", "구간": " buckets", "개": "", "명": " people",
            "년": "", "월": "", "일": "", "개월": " months", "분기": " quarters", "회": " times",
            "차": "", "호": "", "단계": " stages", "등급": " grades", "층": " layers", "곳": "", "배": "x",
            "인": " persons", "개사": " firms", "개국": " countries", "좌": " accounts", "매": "", "점": " points",
            "원": " KRW", "억원": "00m KRW", "억": "00m", "조원": "tn KRW", "조": "tn", "만원": "0k KRW", "만": "0k",
            "천만원": "0m KRW", "천만": "0m", "천원": "k KRW", "천": "k", "백만원": "m KRW", "백만": "m", "십억원": "bn KRW", "십억": "bn"}
_LAW = re.compile(r"^제(\d+)(조|항|편|절|호|관|장)(?:의(\d+))?$")
_LAW_EN = {"조": "Article", "항": "Paragraph", "편": "Part", "절": "Section", "호": "Item", "관": "Subsection", "장": "Chapter"}
_SUB = re.compile(r"^(\d+)\.(가|나|다|라|마|바|사)$")
_SUB_EN = {"가": "a", "나": "b", "다": "c", "라": "d", "마": "e", "바": "f", "사": "g"}
_NAME = re.compile(r"^(김|이|박|최|정|한|오|강|조|윤|장|임)OO$")
_NAME_EN = {"김": "Kim", "이": "Lee", "박": "Park", "최": "Choi", "정": "Jung", "한": "Han", "오": "Oh",
            "강": "Kang", "조": "Cho", "윤": "Yoon", "장": "Jang", "임": "Lim"}
_HEX64 = re.compile(r"\b[0-9a-f]{64}\b")
_HASH_KEY = re.compile(r"(sha256|fingerprint|digest|schema_hash|_hash)$")

MISSES: Counter = Counter()


def _humanize(name: str) -> str:
    return name.replace("_", " ")


def load_dictionary() -> dict[str, str]:
    if DICT_PATH.exists():
        return json.loads(DICT_PATH.read_text(encoding="utf-8"))
    return {}


def load_json(path: Path) -> dict[str, str]:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def js_literals(src: str) -> set[str]:
    """JS 원문에서 한글이 든 문자열 리터럴을 모은다 (화면이 즉석에서 조합하는 UI 문자열의 목록)."""
    out: set[str] = set()
    for rx in _JS_LIT:
        out.update(m.group(1) for m in rx.finditer(src))
    for m in re.finditer(r"`((?:[^`\\]|\\.)*?)`", src):
        for part in re.split(r"\$\{[^}]*\}", m.group(1)):
            if HANGUL.search(part):
                out.add(part.strip())
    return out


def ui_keys(js_src: str) -> list[str]:
    """국내(KR) 기관을 볼 때도 영어로 바꿔도 되는 키: 화면 문자열이지 원장 값이 아닌 것.

    i18n 등록 문자열, JS 리터럴, 카탈로그 컬럼·테이블 이름, 화면 조사에서 모은 즉석 조합 문자열.
    """
    keys: set[str] = set(_i18n.ko_to_en())
    keys |= js_literals(js_src)
    for t in cat.ALL_TABLES:
        keys.add(t.korean)
        for c in t.columns:
            keys.add(c.korean)
    keys |= set(load_json(UI_KEYS_PATH))
    return sorted(k for k in keys if HANGUL.search(k))


def build_map() -> dict[str, str]:
    m: dict[str, str] = {}
    for t in cat.ALL_TABLES:
        if t.korean:
            m.setdefault(t.korean, _humanize(t.name))
        for c in t.columns:
            if c.korean:
                m.setdefault(c.korean, _humanize(c.name))
    m.update(_i18n.ko_to_en())
    m.update(load_dictionary())
    m.update(load_json(SENT_PATH))
    return m


_ENDING = re.compile(r"(다\.|다$|이다|한다|없다|않는다|된다|있다|였다|합니다|니다)")
_PARTICLE = re.compile(r"[가-힣][은는이가을를에로]\s+[가-힣]")
_POSS = re.compile(r"^([가-힣A-Za-z0-9]+)(의|와|과)$")


class _Sentence:
    """문장꼴 판정. 어미가 있으면 문장이고, 조사처럼 보이는 글자는 긴 문자열에서만 센다
    (국가·평가·회사 같은 낱말 끝을 조사로 오인하지 않기 위해서)."""

    @staticmethod
    def search(s: str):
        return _ENDING.search(s) or _PARTICLE.search(s)


_SENTENCE = _Sentence


class Translator:
    """전부 옮길 수 있을 때만 옮긴다. 낱말 몇 개만 영어로 바뀐 문장은 원문보다 못하므로,
    모르는 낱말이 하나라도 있으면 그 문자열은 원문 그대로 둔다. 문장꼴(조사·어미가 있는
    문자열)은 통째로 사전에 있을 때만 옮긴다."""

    def __init__(self, mapping: dict[str, str] | None = None):
        self.m = mapping if mapping is not None else build_map()
        self.fam = load_json(FAM_PATH)
        self.cache: dict[str, str] = {}

    def family(self, s: str) -> str | None:
        """숫자·코드 번호를 # 으로 바꾼 틀이 사전에 있으면 영어 틀에 숫자를 차례로 되돌려 넣는다."""
        nums = _NUMTOK.findall(s)
        if not nums:
            return None
        key = _NUMTOK.sub("#", s)
        en = self.fam.get(key)
        if en is None:
            return None
        it = iter(nums)
        # 영어 틀의 # 은 순서대로, #1·#2 는 그 번호의 숫자로 (어순이 바뀌는 틀)
        return re.sub(r"#(\d)?", lambda m: (nums[int(m.group(1)) - 1] if m.group(1) and int(m.group(1)) <= len(nums)
                                             else next(it, "#")), en)

    def word(self, w: str) -> str | None:
        if w in self.m:
            return self.m[w]
        u = _UNIT.match(w)
        if u:
            return u.group(1) + _UNIT_EN[u.group(2)]
        u = _LAW.match(w)
        if u:
            return _LAW_EN[u.group(2)] + " " + u.group(1) + ("-" + u.group(3) if u.group(3) else "")
        u = _SUB.match(w)
        if u:
            return u.group(1) + "." + _SUB_EN[u.group(2)]
        u = _NAME.match(w)
        if u:
            return _NAME_EN[u.group(1)] + " OO"
        u = _POSS.match(w)                       # 유가증권의 → Securities · 차주재무와 → Borrower financials and
        if u and u.group(1) in self.m:
            return self.m[u.group(1)] + ("" if u.group(2) == "의" else " and")
        return None

    def segment(self, seg: str) -> str | None:
        if seg in self.m:
            return self.m[seg]
        words = seg.split(" ")
        out, i = [], 0
        while i < len(words):
            hit = None
            for j in range(len(words), i, -1):
                phrase = " ".join(words[i:j])
                if phrase in self.m:
                    hit, i = self.m[phrase], j
                    break
            if hit is None:
                w = words[i]
                if HANGUL.search(w):
                    hit = self.word(w)
                    if hit is None:
                        MISSES[w] += 1
                        return None
                else:
                    hit = w
                i += 1
            out.append(hit)
        return " ".join(out)

    def links(self, html_: str) -> str:
        """경영진 요약의 딥링크 앵커 문구를 옮긴다 (→ 자본 스택 등)."""
        return re.sub(r"→ ([^<]+)</a>", lambda m: "→ " + self.text(m.group(1)) + "</a>", html_)

    def templates(self, s: str) -> str | None:
        """엔진이 f-string 으로 만든 경영진 요약·액션 문장은 틀이 정해져 있다. 틀째로 옮긴다."""
        for rx, fn in _TEMPLATES:
            m = rx.match(s)
            if m:
                return fn(self, m)
        return None

    def text(self, s: str) -> str:
        if not HANGUL.search(s):
            return s
        if s in self.cache:
            return self.cache[s]
        t = self.templates(s)
        if t is None:
            t = self.family(s)
        if t is not None:
            r = t
        elif s in self.m:
            r = self.m[s]
        elif _SENTENCE.search(s):
            MISSES[s] += 1
            r = s
        else:
            parts = _SPLIT.split(s)
            done = []
            for part in parts:
                if HANGUL.search(part):
                    core = part.strip()
                    t = self.segment(core)
                    if t is None:
                        done = None
                        break
                    lead = part[:len(part) - len(part.lstrip())]
                    tail = part[len(part.rstrip()):]
                    done.append(lead + t + tail)
                else:
                    done.append(part)
            r = re.sub(r"  +", " ", "".join(done)) if done is not None else s
        self.cache[s] = r
        return r

    def walk(self, x):
        if isinstance(x, str):
            return self.text(x)
        if isinstance(x, dict):
            return {k: self.walk(v) for k, v in x.items()}
        if isinstance(x, list):
            return [self.walk(v) for v in x]
        return x


_VERB = {"즉시 대응": "immediate action", "에스컬레이션": "escalation", "조기경보 모니터링": "early-warning monitoring"}
_TEMPLATES = [
    (re.compile(r"^<b>자본</b> — CET1 (?P<cet1>.+?)로 요구치 대비 (?P<sur>[+\-\d.]+)%p 여유\. RWA의 최대 구성은 <b>(?P<comp>.*?)</b>\((?P<share>\d+)%\)로, 자본비율 방어의 1차 레버는 이 부문의 한도·성장 관리다\. (?P<links>.*)$"),
     lambda t, m: f"<b>Capital</b>: CET1 {m['cet1']}, {m['sur']}%p above the requirement. The largest RWA component is <b>{t.text(m['comp'])}</b> ({m['share']}%), so the first lever for defending the ratio is limit and growth management of that segment. {t.links(m['links'])}"),
    (re.compile(r"^<b>충당금</b> — 확률가중 PIT ECL (?P<pit>.+?)은 TTC (?P<ttc>.+?) 대비 <b>(?P<gap>[+\-\d]+)%</b>\. 거시 하방 시나리오 가중이 충당금을 끌어올리는 국면으로, 분기 적립 계획에 선반영 필요\. (?P<links>.*)$"),
     lambda t, m: f"<b>Provisions</b>: probability-weighted PIT ECL {t.text(m['pit'])} is <b>{m['gap']}%</b> versus TTC {t.text(m['ttc'])}. Macro downside scenario weights are pushing provisions up; reflect this in the quarterly provisioning plan. {t.links(m['links'])}"),
    (re.compile(r"^<b>집중리스크</b> — 최대 집중 차원은 <b>(?P<dim>.*?)</b> \(HHI (?P<hhi>[\d.]+), 최대 버킷 점유 (?P<top>\d+)%\)\.(?P<red>.*?) 분산 없이는 스트레스 손실이 이 차원에 눌려 비선형으로 커진다\. (?P<links>.*)$"),
     lambda t, m: f"<b>Concentration risk</b>: the most concentrated dimension is <b>{t.text(m['dim'])}</b> (HHI {m['hhi']}, largest bucket {m['top']}%).{t.text(m['red'])} Without diversification, stress losses concentrate on this dimension and grow non-linearly. {t.links(m['links'])}"),
    (re.compile(r"^<b>스트레스 회복력</b> — severe 시나리오에서 CET1 저점 <b>(?P<tr>.+?)</b> \((?P<q>.+?)\), (?:<b>(?P<ratio>.+?)</b> 요구치 최초 침범 <b>(?P<bq>.+?)</b>, |요구치 침범 없음, )기말 (?P<end>.+?)로 회복\. 역스트레스 임계 심도 s=(?P<s>[\d.]+) — 현 여력의 소진에는 GDP (?P<gdp>[+\-\d.]+%) 급 충격 필요\. (?P<links>.*)$"),
     lambda t, m: f"<b>Stress resilience</b>: under the severe scenario CET1 troughs at <b>{m['tr']}</b> ({m['q']}), " + (f"with the first breach of the <b>{t.text(m['ratio'])}</b> requirement in <b>{m['bq']}</b>, " if m['ratio'] else "with no breach of the requirement, ") + f"recovering to {m['end']} at period end. Reverse stress threshold severity s={m['s']}; exhausting the current headroom would take a GDP shock of about {m['gdp']}. {t.links(m['links'])}"),
    (re.compile(r"^<b>유동성</b> — LCR (?P<lcr>.+?) / NSFR (?P<nsfr>.+?) \(기준 각 (?P<min>.+?)\)\. 기준 대비 여유는 있으나 LCR은 조기경보 구간이므로 고유동성자산 buffer 소진 속도를 intraday로 모니터링\. (?P<links>.*)$"),
     lambda t, m: f"<b>Liquidity</b>: LCR {m['lcr']} / NSFR {m['nsfr']} (minimum {m['min']} each). There is headroom, but LCR is in the early-warning band, so monitor the HQLA buffer run-off intraday. {t.links(m['links'])}"),
    (re.compile(r"^<b>모형·기타 AMBER</b> — (?P<items>.*?)\. 관리 한계 위반으로 에스컬레이션 대상\. (?P<links>.*)$"),
     lambda t, m: f"<b>Model and other AMBER</b>: {t.text(m['items'])}. Management limit breached; escalate. {t.links(m['links'])}"),
    (re.compile(r"^\[(?P<g>RED|AMBER|WATCH)\] <b>(?P<name>.*?)</b> (?P<verb>즉시 대응|에스컬레이션|조기경보 모니터링) — 실측 (?P<act>.+?) vs board 한계 (?P<thr>.+?) \((?P<cat>.*?), (?P<cit>.*?)\)$"),
     lambda t, m: f"[{m['g']}] <b>{t.text(m['name'])}</b> {_VERB[m['verb']]}: actual {t.text(m['act'])} vs board limit {t.text(m['thr'])} ({t.text(m['cat'])}, {t.text(m['cit'])})"),
    (re.compile(r"^\[(?P<st>WARN|FAIL)\] <b>(?P<name>.*?)</b> — (?P<detail>.*)$"),
     lambda t, m: f"[{m['st']}] <b>{t.text(m['name'])}</b>: {t.text(m['detail'])}"),
]


def scrub_hashes(x):
    """SHA-256·지문·스키마 해시를 없앤다. 표에서는 그 컬럼을 빼고, 값에서는 64자리 16진수를 지운다."""
    if isinstance(x, dict):
        if isinstance(x.get("columns"), list) and isinstance(x.get("rows"), list):
            cols = x["columns"]
            keep = [k for k, c in enumerate(cols) if not _HASH_KEY.search(str(c))]
            if len(keep) != len(cols):
                x = dict(x)
                x["columns"] = [cols[k] for k in keep]
                if isinstance(x.get("labels"), list) and len(x["labels"]) == len(cols):
                    x["labels"] = [x["labels"][k] for k in keep]
                x["rows"] = [[r[k] for k in keep] for r in x["rows"]]
        out = {}
        for k, v in x.items():
            if _HASH_KEY.search(str(k)) and isinstance(v, str):
                out[k] = ""
            else:
                out[k] = scrub_hashes(v)
        return out
    if isinstance(x, list):
        return [scrub_hashes(v) for v in x]
    if isinstance(x, str):
        return _HEX64.sub("", x)
    return x


def remaining_hangul(x, acc: Counter | None = None) -> Counter:
    acc = Counter() if acc is None else acc
    if isinstance(x, str):
        if HANGUL.search(x):
            acc[x] += 1
    elif isinstance(x, dict):
        for v in x.values():
            remaining_hangul(v, acc)
    elif isinstance(x, list):
        for v in x:
            remaining_hangul(v, acc)
    return acc

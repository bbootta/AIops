import Foundation

// 검색 결과 한 건. id는 스냅샷 내 엔트리 인덱스.
struct SearchResult: Identifiable {
    let id: Int
    let path: String
    let name: String
    let parent: String
}

struct SearchOutcome {
    let results: [SearchResult]
    let totalMatches: Int
    let capped: Bool
    let elapsedMS: Double
}

// 크롤 중에 인덱스 버퍼를 점진적으로 쌓는 빌더.
// 경로와 소문자 파일명을 각각 하나의 연속 바이트 버퍼에 이어 붙이고
// 오프셋 배열로 경계를 기록한다. 엔트리당 String 객체를 만들지 않아
// 수백만 파일에서도 메모리와 검색 속도가 유지된다.
final class IndexBuilder {
    private var pathBuf: [UInt8] = []
    private var pathOffsets: [UInt32] = [0]
    private var nameBuf: [UInt8] = []
    private var nameOffsets: [UInt32] = [0]

    init() {
        pathBuf.reserveCapacity(1 << 24)
        nameBuf.reserveCapacity(1 << 22)
        pathOffsets.reserveCapacity(1 << 18)
        nameOffsets.reserveCapacity(1 << 18)
    }

    var count: Int { pathOffsets.count - 1 }

    func add(path: String, lowercasedName: String) {
        pathBuf.append(contentsOf: path.utf8)
        pathOffsets.append(UInt32(pathBuf.count))
        nameBuf.append(contentsOf: lowercasedName.utf8)
        nameOffsets.append(UInt32(nameBuf.count))
    }

    func finish() -> IndexSnapshot {
        IndexSnapshot(pathBuf: pathBuf, pathOffsets: pathOffsets,
                      nameBuf: nameBuf, nameOffsets: nameOffsets)
    }
}

// 불변 인덱스 스냅샷. 생성 후 절대 변경되지 않으므로
// 백그라운드 검색 큐에서 잠금 없이 읽어도 안전하다.
final class IndexSnapshot {
    let pathBuf: [UInt8]
    let pathOffsets: [UInt32]
    let nameBuf: [UInt8]
    let nameOffsets: [UInt32]

    init(pathBuf: [UInt8], pathOffsets: [UInt32], nameBuf: [UInt8], nameOffsets: [UInt32]) {
        self.pathBuf = pathBuf
        self.pathOffsets = pathOffsets
        self.nameBuf = nameBuf
        self.nameOffsets = nameOffsets
    }

    var count: Int { pathOffsets.count - 1 }

    func path(at index: Int) -> String {
        let start = Int(pathOffsets[index])
        let end = Int(pathOffsets[index + 1])
        return String(decoding: pathBuf[start..<end], as: UTF8.self)
    }

    func result(at index: Int) -> SearchResult {
        let p = path(at: index)
        let ns = p as NSString
        return SearchResult(id: index, path: p,
                            name: ns.lastPathComponent,
                            parent: ns.deletingLastPathComponent)
    }

    // MARK: - 검색

    private struct Match {
        let index: Int
        let score: Int
        let nameLen: Int
    }

    // 공백으로 나눈 토큰 전부가 파일명에 포함되면 일치(AND).
    // 점수: 0 완전 일치, 1 접두 일치, 2 부분 일치. 낮을수록 위.
    func search(_ rawQuery: String, limit: Int) -> SearchOutcome {
        let started = Date()
        let tokens = rawQuery.lowercased()
            .split(separator: " ")
            .map { Array($0.utf8) }
            .filter { !$0.isEmpty }
        guard !tokens.isEmpty else {
            return SearchOutcome(results: [], totalMatches: 0, capped: false, elapsedMS: 0)
        }

        let cap = 100_000
        var matches: [Match] = []
        matches.reserveCapacity(4096)
        var capped = false

        nameBuf.withUnsafeBufferPointer { buf in
            let total = count
            outer: for i in 0..<total {
                let start = Int(nameOffsets[i])
                let end = Int(nameOffsets[i + 1])
                var score = 2
                for (t, token) in tokens.enumerated() {
                    let pos = Self.find(buf, start, end, token)
                    if pos < 0 { continue outer }
                    if t == 0 {
                        if pos == start {
                            score = (end - start == token.count) ? 0 : 1
                        } else {
                            score = 2
                        }
                    }
                }
                matches.append(Match(index: i, score: score, nameLen: end - start))
                if matches.count >= cap {
                    capped = true
                    break
                }
            }
        }

        let sorted = matches.sorted(by: Self.better)
        let top = sorted.prefix(limit)
        let results = top.map { result(at: $0.index) }
        let elapsed = Date().timeIntervalSince(started) * 1000
        return SearchOutcome(results: results, totalMatches: matches.count,
                             capped: capped, elapsedMS: elapsed)
    }

    private static func better(_ a: Match, _ b: Match) -> Bool {
        if a.score != b.score { return a.score < b.score }
        if a.nameLen != b.nameLen { return a.nameLen < b.nameLen }
        return a.index < b.index
    }

    private static func find(_ hay: UnsafeBufferPointer<UInt8>, _ start: Int, _ end: Int, _ needle: [UInt8]) -> Int {
        let n = needle.count
        if n == 0 { return start }
        if end - start < n { return -1 }
        let first = needle[0]
        var i = start
        let last = end - n
        while i <= last {
            if hay[i] == first {
                var j = 1
                while j < n, hay[i &+ j] == needle[j] { j &+= 1 }
                if j == n { return i }
            }
            i &+= 1
        }
        return -1
    }

    // MARK: - 인덱싱 대상

    // 기본: 홈 디렉터리 + /Applications.
    // ~/Library/Application Support/FlashFind/roots.txt 가 있으면
    // 거기 적힌 경로들(한 줄에 하나, # 주석)로 대체한다.
    static func indexRoots() -> [URL] {
        let fm = FileManager.default
        if let dir = try? fm.url(for: .applicationSupportDirectory, in: .userDomainMask,
                                 appropriateFor: nil, create: false) {
            let file = dir.appendingPathComponent("FlashFind/roots.txt")
            if let text = try? String(contentsOf: file, encoding: .utf8) {
                let urls = text.split(whereSeparator: \.isNewline)
                    .map { $0.trimmingCharacters(in: .whitespaces) }
                    .filter { !$0.isEmpty && !$0.hasPrefix("#") }
                    .map { URL(fileURLWithPath: ($0 as NSString).expandingTildeInPath) }
                    .filter { fm.fileExists(atPath: $0.path) }
                if !urls.isEmpty { return urls }
            }
        }
        var roots = [fm.homeDirectoryForCurrentUser]
        if fm.fileExists(atPath: "/Applications") {
            roots.append(URL(fileURLWithPath: "/Applications"))
        }
        return roots
    }

    // 전체 크롤. 숨김 파일 포함, 앱/패키지 번들 내부는 제외,
    // 심볼릭 링크는 따라가지 않는다(FileManager 기본 동작).
    static func crawl(progress: (Int) -> Void) -> IndexSnapshot {
        let fm = FileManager.default
        let builder = IndexBuilder()
        for root in indexRoots() {
            guard let enumerator = fm.enumerator(
                at: root,
                includingPropertiesForKeys: [],
                options: [.skipsPackageDescendants],
                errorHandler: { _, _ in true }
            ) else { continue }
            for case let url as URL in enumerator {
                builder.add(path: url.path, lowercasedName: url.lastPathComponent.lowercased())
                if builder.count % 25_000 == 0 { progress(builder.count) }
            }
        }
        return builder.finish()
    }

    // MARK: - 캐시 (기계 로컬, 리틀 엔디언 고정 포맷)

    private static let magic = Array("FLASHFINDIDX1".utf8)

    static func cacheURL() throws -> URL {
        let base = try FileManager.default.url(for: .applicationSupportDirectory,
                                               in: .userDomainMask,
                                               appropriateFor: nil, create: true)
        let dir = base.appendingPathComponent("FlashFind", isDirectory: true)
        try FileManager.default.createDirectory(at: dir, withIntermediateDirectories: true)
        return dir.appendingPathComponent("index.bin")
    }

    func saveCache() {
        guard count > 0, let url = try? Self.cacheURL() else { return }
        var data = Data()
        data.reserveCapacity(pathBuf.count + nameBuf.count
                             + (pathOffsets.count + nameOffsets.count) * 4 + 64)
        data.append(contentsOf: Self.magic)
        Self.append(UInt64(count), to: &data)
        Self.append(UInt64(pathBuf.count), to: &data)
        Self.append(UInt64(nameBuf.count), to: &data)
        Self.append(pathBuf, to: &data)
        Self.append(nameBuf, to: &data)
        Self.append(pathOffsets, to: &data)
        Self.append(nameOffsets, to: &data)
        try? data.write(to: url, options: .atomic)
    }

    static func loadCache() -> IndexSnapshot? {
        guard let url = try? cacheURL(),
              let data = try? Data(contentsOf: url, options: .mappedIfSafe) else { return nil }
        var off = 0
        guard data.count >= magic.count + 24,
              Array(data.prefix(magic.count)) == magic else { return nil }
        off = magic.count

        func readBytes(_ n: Int) -> [UInt8]? {
            guard n >= 0, off + n <= data.count else { return nil }
            let arr = [UInt8](data[off..<(off + n)])
            off += n
            return arr
        }
        func readU64() -> UInt64? {
            guard let b = readBytes(8) else { return nil }
            var v: UInt64 = 0
            for i in 0..<8 { v |= UInt64(b[i]) << (8 * i) }
            return v
        }
        func readU32s(_ n: Int) -> [UInt32]? {
            guard n >= 0, n < Int.max / 4, let bytes = readBytes(n * 4) else { return nil }
            var arr = [UInt32](repeating: 0, count: n)
            bytes.withUnsafeBytes { raw in
                arr.withUnsafeMutableBytes { dst in
                    dst.copyMemory(from: raw)
                }
            }
            return arr
        }

        guard let countU = readU64(), let pathLen = readU64(), let nameLen = readU64(),
              countU > 0, countU < 50_000_000,
              pathLen < 4_000_000_000, nameLen < 4_000_000_000 else { return nil }
        let count = Int(countU)
        guard let pathBuf = readBytes(Int(pathLen)),
              let nameBuf = readBytes(Int(nameLen)),
              let pathOffsets = readU32s(count + 1),
              let nameOffsets = readU32s(count + 1),
              pathOffsets.first == 0, nameOffsets.first == 0,
              Int(pathOffsets.last ?? 1) == pathBuf.count,
              Int(nameOffsets.last ?? 1) == nameBuf.count
        else { return nil }
        return IndexSnapshot(pathBuf: pathBuf, pathOffsets: pathOffsets,
                             nameBuf: nameBuf, nameOffsets: nameOffsets)
    }

    private static func append(_ value: UInt64, to data: inout Data) {
        var v = value.littleEndian
        withUnsafeBytes(of: &v) { data.append(contentsOf: $0) }
    }

    private static func append(_ bytes: [UInt8], to data: inout Data) {
        bytes.withUnsafeBufferPointer { buf in
            data.append(buf)
        }
    }

    private static func append(_ values: [UInt32], to data: inout Data) {
        values.withUnsafeBufferPointer { buf in
            buf.withMemoryRebound(to: UInt8.self) { data.append($0) }
        }
    }
}

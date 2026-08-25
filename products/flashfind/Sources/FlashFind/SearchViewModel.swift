import AppKit
import Foundation

// UI 상태와 인덱스 수명주기를 관리한다.
// @Published 프로퍼티는 전부 메인 스레드에서만 쓴다.
final class SearchViewModel: ObservableObject {
    @Published var query: String = "" {
        didSet { scheduleSearch() }
    }
    @Published var results: [SearchResult] = []
    @Published var selection: Int? = nil
    @Published var statusText: String = "인덱스 준비 중"
    @Published var isIndexing: Bool = false

    private var snapshot: IndexSnapshot?
    private var indexSummary: String = ""
    private var pendingSearch: DispatchWorkItem?
    private var searchGeneration = 0
    private var keyMonitor: Any?
    private var started = false
    private let searchQueue = DispatchQueue(label: "flashfind.search", qos: .userInitiated)

    private static let numberFormatter: NumberFormatter = {
        let f = NumberFormatter()
        f.numberStyle = .decimal
        return f
    }()

    private static func fmt(_ n: Int) -> String {
        numberFormatter.string(from: NSNumber(value: n)) ?? String(n)
    }

    // MARK: - 수명주기

    func start() {
        guard !started else { return }
        started = true
        installKeyMonitor()
        DispatchQueue.global(qos: .userInitiated).async { [weak self] in
            guard let self else { return }
            if let cached = IndexSnapshot.loadCache() {
                self.adopt(snapshot: cached, note: "캐시, 백그라운드에서 다시 스캔 중")
            }
            self.rebuildIndex()
        }
    }

    func reindex() {
        guard !isIndexing else { return }
        DispatchQueue.global(qos: .userInitiated).async { [weak self] in
            self?.rebuildIndex()
        }
    }

    private func rebuildIndex() {
        DispatchQueue.main.async { self.isIndexing = true }
        let startTime = Date()
        let snap = IndexSnapshot.crawl { [weak self] n in
            DispatchQueue.main.async {
                self?.statusText = "인덱싱 중: \(Self.fmt(n))개"
            }
        }
        snap.saveCache()
        let secs = Date().timeIntervalSince(startTime)
        adopt(snapshot: snap, note: String(format: "%.1f초 스캔", secs))
        DispatchQueue.main.async { self.isIndexing = false }
    }

    private func adopt(snapshot snap: IndexSnapshot, note: String) {
        DispatchQueue.main.async {
            self.snapshot = snap
            self.indexSummary = "\(Self.fmt(snap.count))개 파일 인덱스됨 (\(note))"
            if self.query.trimmingCharacters(in: .whitespaces).isEmpty {
                self.statusText = self.indexSummary
            } else {
                self.scheduleSearch()
            }
        }
    }

    // MARK: - 검색

    private func scheduleSearch() {
        pendingSearch?.cancel()
        searchGeneration += 1
        let gen = searchGeneration
        let q = query

        if q.trimmingCharacters(in: .whitespaces).isEmpty {
            results = []
            selection = nil
            if !indexSummary.isEmpty { statusText = indexSummary }
            return
        }
        guard let snap = snapshot else { return }

        let item = DispatchWorkItem { [weak self] in
            guard let self else { return }
            let outcome = snap.search(q, limit: 300)
            DispatchQueue.main.async {
                guard self.searchGeneration == gen else { return }
                self.results = outcome.results
                self.selection = outcome.results.isEmpty ? nil : 0
                var text = "\(Self.fmt(outcome.totalMatches))개"
                if outcome.capped { text += " 이상" }
                text += String(format: " 일치 · %.0f ms", outcome.elapsedMS)
                self.statusText = text
            }
        }
        pendingSearch = item
        searchQueue.asyncAfter(deadline: .now() + 0.05, execute: item)
    }

    // MARK: - 결과에 대한 동작

    func open(_ r: SearchResult) {
        NSWorkspace.shared.open(URL(fileURLWithPath: r.path))
    }

    func reveal(_ r: SearchResult) {
        NSWorkspace.shared.activateFileViewerSelecting([URL(fileURLWithPath: r.path)])
    }

    func copyPath(_ r: SearchResult) {
        let pb = NSPasteboard.general
        pb.clearContents()
        pb.setString(r.path, forType: .string)
    }

    // MARK: - 키보드

    private func installKeyMonitor() {
        DispatchQueue.main.async {
            self.keyMonitor = NSEvent.addLocalMonitorForEvents(matching: .keyDown) { [weak self] event in
                guard let self else { return event }
                return self.handle(event)
            }
        }
    }

    // 반환값 nil이면 이벤트를 소비한다.
    private func handle(_ event: NSEvent) -> NSEvent? {
        let cmd = event.modifierFlags.contains(.command)
        switch event.keyCode {
        case 125 where !cmd:  // 아래 화살표
            guard !results.isEmpty else { return event }
            move(1)
            return nil
        case 126 where !cmd:  // 위 화살표
            guard !results.isEmpty else { return event }
            move(-1)
            return nil
        case 36:              // Return
            guard let r = selectedResult() else { return event }
            if cmd { reveal(r) } else { open(r) }
            return nil
        case 53:              // Escape
            guard !query.isEmpty else { return event }
            query = ""
            return nil
        default:
            return event
        }
    }

    private func move(_ delta: Int) {
        guard !results.isEmpty else { return }
        let current = selection ?? -1
        selection = min(max(current + delta, 0), results.count - 1)
    }

    private func selectedResult() -> SearchResult? {
        if let sel = selection, results.indices.contains(sel) {
            return results[sel]
        }
        return results.first
    }

    deinit {
        if let keyMonitor {
            NSEvent.removeMonitor(keyMonitor)
        }
    }
}

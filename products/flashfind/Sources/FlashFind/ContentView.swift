import SwiftUI
import AppKit

struct ContentView: View {
    @EnvironmentObject var model: SearchViewModel
    @FocusState private var searchFocused: Bool

    var body: some View {
        VStack(spacing: 0) {
            searchBar
            Divider()
            resultList
            Divider()
            statusBar
        }
        .frame(minWidth: 720, minHeight: 440)
        .onAppear {
            model.start()
            DispatchQueue.main.asyncAfter(deadline: .now() + 0.2) {
                searchFocused = true
            }
        }
    }

    private var searchBar: some View {
        HStack(spacing: 8) {
            Image(systemName: "magnifyingglass")
                .foregroundColor(.secondary)
            TextField("파일 이름 검색 (스페이스로 AND 검색)", text: $model.query)
                .textFieldStyle(.plain)
                .font(.system(size: 17))
                .focused($searchFocused)
                .autocorrectionDisabled()
            if !model.query.isEmpty {
                Button {
                    model.query = ""
                } label: {
                    Image(systemName: "xmark.circle.fill")
                        .foregroundColor(.secondary)
                }
                .buttonStyle(.plain)
            }
        }
        .padding(EdgeInsets(top: 12, leading: 14, bottom: 12, trailing: 14))
    }

    private var resultList: some View {
        ScrollViewReader { proxy in
            List(selection: $model.selection) {
                ForEach(Array(model.results.enumerated()), id: \.offset) { index, item in
                    ResultRow(item: item)
                        .tag(index)
                        .contentShape(Rectangle())
                        .onTapGesture(count: 2) { model.open(item) }
                        .contextMenu {
                            Button("열기") { model.open(item) }
                            Button("Finder에서 보기") { model.reveal(item) }
                            Divider()
                            Button("경로 복사") { model.copyPath(item) }
                        }
                }
            }
            .listStyle(.plain)
            .overlay {
                if model.results.isEmpty {
                    Text(model.query.isEmpty ? "입력하는 즉시 검색됩니다" : "결과 없음")
                        .foregroundColor(.secondary)
                }
            }
            .onChange(of: model.selection) { sel in
                if let sel {
                    proxy.scrollTo(sel)
                }
            }
        }
    }

    private var statusBar: some View {
        HStack {
            Text(model.statusText)
                .font(.system(size: 11))
                .foregroundColor(.secondary)
                .lineLimit(1)
            Spacer()
            Button("다시 인덱싱") { model.reindex() }
                .font(.system(size: 11))
                .disabled(model.isIndexing)
        }
        .padding(EdgeInsets(top: 6, leading: 14, bottom: 6, trailing: 14))
    }
}

struct ResultRow: View {
    let item: SearchResult

    var body: some View {
        HStack(spacing: 8) {
            Image(nsImage: NSWorkspace.shared.icon(forFile: item.path))
                .resizable()
                .frame(width: 18, height: 18)
            VStack(alignment: .leading, spacing: 1) {
                Text(item.name)
                    .font(.system(size: 13))
                    .lineLimit(1)
                Text(item.parent)
                    .font(.system(size: 11))
                    .foregroundColor(.secondary)
                    .lineLimit(1)
                    .truncationMode(.middle)
            }
        }
        .padding(.vertical, 1)
    }
}

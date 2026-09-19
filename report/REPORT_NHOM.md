# Báo Cáo Nhóm — Lab 7: Embedding & Vector Store

**Nhóm:** Data Foundations

**Thành viên:**

- Bùi Trọng Trinh — 2A202602861
- Nguyễn Lê Phúc Thắng — 2A202602638
- Lê Duy Quân — 2A202602731
- Vũ Minh Hoàng — 2A202602371

**Ngày:** 19/09/2026

Nhóm thống nhất dùng cùng corpus, cùng năm benchmark query, cùng lexical hashing embedder và chỉ thay đổi chiến lược chunking. Cách kiểm soát này giúp chênh lệch kết quả phản ánh chiến lược chunking thay vì khác dữ liệu hoặc embedding backend.

## 1. Lựa chọn tài liệu — 10/10

### Chủ đề và lý do chọn

**Chủ đề:** Quyền mượn và dịch vụ thư viện VinUniversity.

Chủ đề có quy định định lượng rõ (số tài liệu, thời hạn, số lần gia hạn, thời gian giữ yêu cầu) nên tạo được gold answer kiểm chứng trực tiếp. Chính sách cũng phân biệt sinh viên và giảng viên, phù hợp để đánh giá metadata filter thay vì chỉ gắn metadata cho có.

### Data Inventory

| # | Tài liệu | Nguồn | Ngày lấy / phiên bản | Ký tự thân bài | Metadata chính |
|---|---|---|---|---:|---|
| 1 | Quyền mượn của giảng viên | [Library Access & Services Policy](https://policy.vinuni.edu.vn/wp-content/uploads/2025/07/POL-LLR-001-V4.0_Library-Access-Services-Policy_9.7.2025_Clean.pdf) | 2026-09-19 / V4.0, 09-07-2025 | 639 | `faculty`, `borrowing` |
| 2 | Quyền mượn của sinh viên đại học | Cùng chính sách V4.0 | 2026-09-19 / V4.0 | 556 | `student`, `borrowing` |
| 3 | Loại tài liệu và gia hạn | Cùng chính sách V4.0 | 2026-09-19 / V4.0 | 831 | `all`, `circulation` |
| 4 | Yêu cầu tài liệu đang được mượn | Cùng chính sách V4.0 | 2026-09-19 / V4.0 | 556 | `all`, `requests` |
| 5 | Tài nguyên điện tử và in ấn | Cùng chính sách V4.0 | 2026-09-19 / V4.0 | 668 | `all`, `electronic-resources` |
| 6 | Thiết bị và phòng chức năng | Cùng chính sách V4.0 | 2026-09-19 / V4.0 | 725 | `all`, `facilities` |
| 7 | Sinh viên tự mượn/trả sách | [International Student Handbook](https://vinuni.edu.vn/wp-content/uploads/2025/04/INTERNATIONAL-STUDENT-HANDBOOK.pdf) | 2026-09-19 / `not-stated` | 689 | `student`, `borrowing-procedure` |

Các file là bản làm sạch và diễn đạt lại ngắn gọn theo từng chủ đề từ nguồn công khai; menu, footer và nội dung không liên quan đã bị loại. Một chính sách được tách thành các đơn vị retrieval, đặc biệt tách quyền của faculty/student để filter theo audience hoạt động thật.

**Data governance checklist**

- [x] Chỉ dùng nguồn công khai chính thức; không có dữ liệu cá nhân, thông tin đăng nhập hoặc tài liệu nội bộ.
- [x] Cả 7 file có `doc_id`, `title`, `source_url`, `retrieved_at`, `document_version`, `audience` và trường lọc bổ sung.
- [x] `sources.csv` khớp một-một với 7 file Markdown.
- [x] `audience` có ba giá trị `student`, `faculty`, `all`.
- [x] Phiên bản không được nguồn nêu được ghi `not-stated`, không suy đoán.

### Metadata schema

| Trường | Kiểu | Ví dụ | Công dụng retrieval |
|---|---|---|---|
| `doc_id` | string | `02-undergraduate-borrowing` | Nhóm mọi chunk về file gốc, hỗ trợ delete và đối chiếu gold doc. |
| `title` | string | `Quyền mượn tài liệu của sinh viên đại học VinUni` | Hiển thị nguồn dễ đọc trong context/prompt. |
| `source_url` | URL string | URL policy PDF | Truy vết về nguồn công khai chính thức. |
| `retrieved_at` | date string | `2026-09-19` | Biết thời điểm snapshot dữ liệu. |
| `document_version` | string | `POL-LLR-001-V4.0 (2025-07-09)` | Phân biệt phiên bản chính sách. |
| `audience` | enum | `student`, `faculty`, `all` | Lọc đúng đối tượng trước khi similarity search. |
| `department` | string | `library` | Mở rộng corpus vẫn lọc được đơn vị cung cấp dịch vụ. |
| `category` | string | `borrowing`, `facilities` | Thu hẹp theo nghiệp vụ. |
| `language` | string | `vi` | Chọn ngôn ngữ phù hợp với câu hỏi/model. |

## 2. Thiết kế chiến lược — 15/15

### Baseline Analysis

`ChunkingStrategyComparator().compare(..., chunk_size=420)` được chạy sau khi bỏ frontmatter:

| Tài liệu | Strategy | Số chunk | Độ dài TB | Nhận xét mạch lạc |
|---|---|---:|---:|---|
| Undergraduate borrowing | FixedSize | 2 | 299.0 | Có overlap nhưng có thể cắt heading/câu. |
| Undergraduate borrowing | Sentence | 2 | 276.5 | Giữ nguyên câu, khá mạch lạc. |
| Undergraduate borrowing | Recursive | 2 | 277.0 | Ưu tiên biên heading/đoạn. |
| Materials & renewal | FixedSize | 3 | 305.0 | Nội dung biên chunk bị lặp. |
| Materials & renewal | Sentence | 3 | 275.3 | Mỗi chunk gồm các câu hoàn chỉnh. |
| Materials & renewal | Recursive | 3 | 275.7 | Giữ đoạn tốt, ít cắt giữa câu. |
| Rooms & equipment | FixedSize | 2 | 383.5 | Ít chunk nhưng trộn hai chủ đề. |
| Rooms & equipment | Sentence | 2 | 361.0 | Đủ câu nhưng có thể trộn section. |
| Rooms & equipment | Recursive | 3 | 240.3 | Tách đúng paragraph nhưng thông tin liên quan có thể rời nhau. |

### Chiến lược của từng thành viên

**Bùi Trọng Trinh — Heading + Recursive fallback**

- Tách trước mỗi heading Markdown vì mỗi mục chính sách là một đơn vị ngữ nghĩa.
- Section dài hơn 420 ký tự được chia recursive; heading được gắn lại vào mọi mảnh con để không mất chủ đề.

```python
sections = re.split(r"(?=^#{1,6}\s)", text, flags=re.MULTILINE)
for section in sections:
    if len(section) <= chunk_size:
        chunks.append(section)
    else:
        for piece in RecursiveChunker(chunk_size=body_size).chunk(body):
            chunks.append(f"{heading}\n{piece}")
```

**Nguyễn Lê Phúc Thắng — FixedSize(420, overlap=80)**

- Có overlap để giảm mất nội dung tại biên và tạo ít chunk nhất.
- Điểm yếu là cắt theo ký tự, không hiểu ranh giới mục của chính sách.

**Lê Duy Quân — Sentence(max_sentences=3)**

- Giữ nguyên câu, số chunk thấp và đạt điểm retrieval ngang Heading.
- Độ dài chunk biến động và các câu từ hai heading liền kề có thể bị ghép.

**Vũ Minh Hoàng — Recursive(chunk_size=420)**

- Ưu tiên paragraph rồi mới xuống câu/từ; tổng quát tốt khi tài liệu không có heading.
- Một số điều kiện liên quan nằm ở hai paragraph nên bị tách khỏi nhau.

### So sánh trên cùng 5 query

| Thành viên | Strategy | Số chunk | Điểm retrieval | Điểm mạnh | Điểm yếu |
|---|---|---:|---:|---|---|
| Nguyễn Lê Phúc Thắng | FixedSize | 15 | 7/10 | Ít chunk, có overlap | Cắt biên ngữ nghĩa |
| Lê Duy Quân | Sentence | 16 | 9/10 | Hiệu quả, câu hoàn chỉnh | Không giữ cấu trúc heading |
| Vũ Minh Hoàng | Recursive | 17 | 7/10 | Tổng quát, giữ paragraph | Có thể tách các điều kiện liên quan |
| Bùi Trọng Trinh | Heading | 29 | 9/10 | Truy vết section rõ, đúng 4/5 top-1 | Nhiều chunk, section ngắn cạnh nhau bị tách |

Chiến lược của Lê Duy Quân (Sentence) và Bùi Trọng Trinh (Heading) cùng đạt 9/10. Với văn bản quy định, nhóm chọn **Heading** làm chiến lược chính vì kết quả có nhãn mục rõ ràng, dễ kiểm chứng nguồn; nếu tối ưu chi phí embedding thì Sentence là lựa chọn tốt hơn do chỉ tạo 16 thay vì 29 chunk.

## 3. Câu hỏi đánh giá và chất lượng truy xuất — 9/10

| # | Query | Gold answer | Chunk chứa thông tin |
|---|---|---|---|
| 1 | Tôi được mượn tối đa bao nhiêu tài liệu và trong bao lâu? | Sinh viên đại học: 3 tài liệu, 2 tuần. | `02-undergraduate-borrowing`, mục Hạn mức và thời hạn |
| 2 | Thời gian gia hạn được tính thế nào và cần điều kiện gì? | Một nửa thời hạn ban đầu; chưa quá hạn và không có người khác yêu cầu. | `03-material-types-and-renewal`, mục Gia hạn |
| 3 | Course Reserve được mượn tối đa bao lâu và bao nhiêu cuốn? | 2 giờ, 1 cuốn/người/lần. | `03-material-types-and-renewal`, mục Course Reserve |
| 4 | Tài liệu yêu cầu được giữ bao lâu trước khi hủy? | 2 ngày. | `04-requesting-items`, mục Nhận tài liệu |
| 5 | Đặt phòng trước bao lâu và đến muộn bao nhiêu phút thì bị hủy? | Tối đa 1 tuần; quá 10 phút thì hủy. | `06-rooms-and-equipment`, hai mục Đặt phòng và Vắng mặt |

### Tổng hợp

| # | Strategy tốt nhất | Có đáp án trong top-3? | Điểm | Ghi chú |
|---|---|---|---:|---|
| 1 | Heading + `audience=student` | Có, top-1 | 2 | Filter là điều kiện để Heading tìm được gold chunk. |
| 2 | Heading/Sentence | Có, top-1 | 2 | Heading “Gia hạn” trùng đúng ý query. |
| 3 | Heading/Sentence | Có, top-1 | 2 | Mục Course Reserve giữ đủ hai con số. |
| 4 | Heading/Sentence | Có, top-1 | 2 | Mục Nhận tài liệu chứa trọn câu trả lời. |
| 5 | Tất cả | Có, nhưng không đủ ở top-1 | 1 | “1 tuần” và “10 phút” nằm ở hai section/chunk. |

### A/B metadata filter

Q1 là câu mơ hồ cố ý không nói người hỏi là sinh viên hay giảng viên. Với Heading, không filter thì top-3 là các tài liệu `all` và hoàn toàn thiếu gold answer; có `{"audience": "student"}` thì `02-undergraduate-borrowing` lên top-1. Với Fixed và Recursive, filter cải thiện gold từ top-2 lên top-1; Sentence vốn có gold top-1 nhưng filter loại bỏ hai kết quả nhiễu phía sau. Như vậy filter tăng precision, nhưng cũng có nguy cơ giảm recall nếu một quy định chung chỉ gắn `audience=all` mà truy vấn lại lọc cứng `student`.

## 4. Demo và bài học nhóm — 4/5

### Nội dung demo chuẩn bị

1. Bùi Trọng Trinh giới thiệu corpus, metadata và chạy `conda run -n lab-vin-env python bench.py --all --strategy heading`.
2. Nguyễn Lê Phúc Thắng và Vũ Minh Hoàng giải thích sự đánh đổi của FixedSize và Recursive so với cấu trúc văn bản quy định.
3. Lê Duy Quân trình bày Sentence đạt 9/10 với 16 chunk; sau đó nhóm demo Q1 có/không có `audience=student` và failure case Q5.

### Bài học

- Điểm theo `doc_id` thôi là chưa đủ: Q5 đúng tài liệu nhưng top-1 không đủ trả lời cả hai vế.
- Metadata chỉ hữu ích khi corpus được tách đúng đối tượng; file gộp student/faculty với `audience=all` sẽ làm filter vô nghĩa.
- Heading tăng traceability nhưng tạo nhiều chunk; Sentence đạt cùng 9/10 với chi phí thấp hơn.

Nếu làm lại, nhóm sẽ thêm cơ chế gộp các section ngắn liền kề hoặc “parent context”: retrieval vẫn ở section nhỏ nhưng agent nhận thêm section trước/sau. Nhóm cũng sẽ chạy thêm semantic embedding đa ngữ; lexical hashing hiện tại có thể bỏ lỡ câu đồng nghĩa không chia sẻ từ khóa.

## Tự đánh giá

| Tiêu chí | Điểm tự đánh giá |
|---|---:|
| Lựa chọn tài liệu | 10 / 10 |
| Thiết kế chiến lược | 15 / 15 |
| Chất lượng truy xuất | 9 / 10 |
| Thuyết trình (đã chuẩn bị kịch bản, chưa thể xác nhận demo trực tiếp) | 4 / 5 |
| **Tổng phần nhóm** | **38 / 40** |

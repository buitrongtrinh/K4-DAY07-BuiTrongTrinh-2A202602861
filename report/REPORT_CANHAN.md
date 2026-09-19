# Báo Cáo Cá Nhân — Lab 7: Embedding & Vector Store

**Họ tên:** Bùi Trọng Trinh

**MSSV:** 2A202602861

**Nhóm:** Data Foundations (bản thực hiện cá nhân)

**Ngày:** 19/09/2026

## 1. Khởi động (Warm-up) — 5/5

### Độ tương tự cosine

Cosine similarity cao nghĩa là hai vector có hướng gần nhau, nên hai đoạn văn được embedding biểu diễn là gần nhau về nội dung dù cách dùng từ có thể khác. Điểm gần 1 là rất tương đồng, gần 0 là ít liên quan và gần -1 là ngược hướng.

**Ví dụ tương đồng cao**

- Câu A: “Sinh viên có thể kéo dài thời hạn mượn sách.”
- Câu B: “Người học được phép gia hạn tài liệu thư viện.”
- Hai câu khác từ vựng nhưng cùng nói về quyền gia hạn tài liệu.

**Ví dụ tương đồng thấp**

- Câu A: “Thư viện giữ sách được yêu cầu trong hai ngày.”
- Câu B: “Mạng nơ-ron học đặc trưng từ dữ liệu.”
- Hai câu thuộc hai chủ đề và mục đích hoàn toàn khác nhau.

Cosine phù hợp hơn Euclidean cho text embedding vì nó tập trung vào hướng (mẫu ngữ nghĩa) thay vì độ lớn vector. Độ dài văn bản hoặc chuẩn hóa vector vì thế ít làm sai lệch phép so sánh.

### Bài toán chunking

Với `chunk_size=500`, `overlap=50`, bước trượt là `500-50=450`:

```text
ceil((10000 - 50) / (500 - 50))
= ceil(9950 / 450)
= 23 chunks
```

Kết quả đã kiểm lại bằng `FixedSizeChunker`: **23 chunks**.

Khi overlap tăng lên 100, bước trượt còn 400:

```text
ceil((10000 - 100) / (500 - 100)) = ceil(9900 / 400) = 25 chunks
```

Số chunk tăng từ 23 lên 25. Overlap lớn tốn thêm lưu trữ và embedding nhưng giảm nguy cơ một ý hoặc câu trả lời bị cắt đúng tại biên chunk.

## 2. Hướng tiếp cận của tôi — 10/10

### Các hàm chunking

`SentenceChunker.chunk` dùng regex `(?<=[.!?])(?:[ \t]+|\n+)` để tách sau dấu kết câu, nhờ vậy dấu câu vẫn nằm trong câu. Hàm trả `[]` cho chuỗi rỗng và gom tối đa số câu được cấu hình. Hạn chế đã biết: viết tắt như “TS.” và số thập phân đứng trước khoảng trắng có thể bị nhận diện sai.

`RecursiveChunker` thử separator theo thứ tự đoạn → dòng → câu → từ → cắt cứng. Mảnh quá dài được đệ quy với separator ưu tiên thấp hơn; các mảnh nhỏ liền kề được gom lại tới gần `chunk_size`. Ba base case là text đã đủ ngắn, hết separator và separator rỗng; hai trường hợp cuối cắt cứng để luôn tiến tới kết thúc.

`compute_similarity` tính dot product chia tích hai chuẩn L2 và trả `0.0` nếu một vector có độ lớn bằng 0. `ChunkingStrategyComparator` chạy ba chunker trên cùng đầu vào và trả `count`, `avg_length`, `chunks`, có chặn chia cho 0.

### EmbeddingStore

Store dùng duy nhất backend in-memory để hành vi không phụ thuộc máy có cài ChromaDB hay không. `_make_record` sao chép metadata, bổ sung `doc_id` nếu thiếu và lưu embedding; `_search_records` tính dot product với query embedding, sắp xếp giảm dần rồi loại embedding khỏi kết quả trả về.

`search_with_filter` lọc ứng viên theo toàn bộ cặp key/value **trước** khi xếp hạng, tránh để tài liệu sai đối tượng chiếm hết top-k. `delete_document` xóa mọi chunk có cùng `metadata['doc_id']` và trả về boolean cho biết có record bị xóa hay không.

### KnowledgeBaseAgent

`answer` truy xuất top-k, đánh số từng context `[1]`, `[2]`, kèm tiêu đề và URL/doc_id nguồn. Prompt yêu cầu chỉ dùng context, nói rõ khi thiếu thông tin và trích dẫn số nguồn. Nếu store rỗng, agent trả thông báo trực tiếp và không gọi LLM.

## 3. Hoàn thiện code — 30/30

Chạy trong đúng môi trường được yêu cầu:

```text
$ conda run -n lab-vin-env python -m pytest tests/ -v
============================= test session starts ==============================
collected 42 items

tests/test_solution.py ..........................................          [100%]

============================== 42 passed in 0.03s ==============================
```

**Số lượng test vượt qua:** 42 / 42

`conda run -n lab-vin-env python main.py "Chunking là gì?"` cũng chạy từ đầu đến cuối, nạp 5 file mẫu, lưu 5 document, search top-3 và gọi demo agent thành công.

## 4. Dự đoán độ tương tự — 5/5

Các điểm dưới đây được đo bằng `LexicalHashEmbedder` trong `bench.py`, không phải model semantic. “Cao/thấp” là so sánh tương đối trong năm cặp.

| Cặp | Câu A | Câu B | Dự đoán | Điểm thực tế | Đúng? |
|---|---|---|---|---:|---|
| 1 | Sinh viên được mượn ba tài liệu trong hai tuần. | Hạn mượn của sinh viên đại học là 3 cuốn trong 2 tuần. | Cao | 0.2962 | Có |
| 2 | Gia hạn chỉ được phép khi không có người khác yêu cầu. | Có thể kéo dài hạn mượn nếu tài liệu chưa bị người khác đặt. | Cao | 0.2646 | Có |
| 3 | Phòng học nhóm được đặt trước qua Outlook. | Thiết bị quá hạn năm ngày được xem là bị mất. | Thấp | 0.0769 | Có |
| 4 | Sách Course Reserve chỉ được mượn trong hai giờ. | Tạp chí in chỉ được đọc tại thư viện. | Thấp | 0.1345 | Có |
| 5 | Người dùng đến muộn quá mười phút sẽ mất lượt đặt phòng. | Sinh viên phải quét thẻ tại máy tự phục vụ để mượn sách. | Thấp | 0.0870 | Có |

Điều đáng chú ý là cặp 1 cùng nghĩa nhưng chỉ đạt 0.2962 vì “ba/cuốn” và “3/tài liệu” không hoàn toàn trùng token. Điều này cho thấy lexical hashing đủ để benchmark có kiểm soát nhưng không thay thế embedding semantic đa ngữ; model semantic sẽ nhận ra các cách diễn đạt tương đương tốt hơn.

## 5. Kết quả truy xuất của tôi — 9/10

Chiến lược cá nhân là `HeadingChunker(chunk_size=420)`: tách theo heading Markdown; section quá dài được chia bằng `RecursiveChunker` và gắn lại heading vào mọi mảnh con. Backend benchmark là lexical hashing 4096 chiều, xác định và không cần API key.

| # | Câu hỏi | Top-1 chunk | Score | Liên quan? | Câu trả lời extractive |
|---|---|---|---:|---|---|
| 1 | Tôi được mượn tối đa bao nhiêu tài liệu và trong bao lâu? | Sinh viên đại học: hạn mức và thời hạn | 0.2985 | Có | 3 tài liệu trong 2 tuần; gia hạn 1 lần. |
| 2 | Thời gian gia hạn được tính thế nào và cần điều kiện gì? | Mục Gia hạn | 0.5180 | Có | Một nửa thời hạn ban đầu; chưa quá hạn và không có người khác yêu cầu. |
| 3 | Course Reserve được mượn bao lâu và bao nhiêu cuốn? | Mục Course Reserve | 0.4331 | Có | 1 cuốn mỗi lần trong 2 giờ. |
| 4 | Tài liệu yêu cầu được giữ bao lâu? | Mục Nhận tài liệu | 0.4989 | Có | Giữ 2 ngày, sau đó yêu cầu bị hủy. |
| 5 | Đặt phòng trước bao lâu và trễ bao nhiêu phút thì hủy? | Heading chung của tài liệu phòng/thiết bị | 0.4336 | Một phần | Ý “10 phút” ở top-3 nhưng ý “1 tuần” nằm chunk khác, nên top-1 không đủ trả lời. |

**Top-3 có chunk chứa đáp án:** 5 / 5.

**Điểm theo rubric:** 9 / 10.

### A/B metadata filter

Q1 cố ý không nêu người hỏi là sinh viên hay giảng viên. Không filter, top-3 lần lượt là `04-requesting-items` và hai chunk `03-material-types-and-renewal`, không chứa hạn mức đúng. Với `metadata_filter={"audience": "student"}`, cả ba kết quả thuộc `02-undergraduate-borrowing` và top-1 trả đúng “3 tài liệu, 2 tuần”. Filter vì thế tăng precision rõ rệt, nhưng chỉ an toàn khi metadata và cách tách tài liệu đúng đối tượng.

### Điều học được

Heading chunking tăng khả năng truy vết vì mỗi kết quả có tiêu đề mục rõ ràng, nhưng Q5 cho thấy tách section quá mạnh có thể làm hai điều kiện liên quan rơi vào hai chunk. Lần sau tôi sẽ gộp section ngắn liền kề hoặc thêm overlap theo heading để giữ cả “đặt trước 1 tuần” và “no-show 10 phút” trong cùng context.

## Tự đánh giá

| Tiêu chí | Điểm tự đánh giá |
|---|---:|
| Khởi động | 5 / 5 |
| Hướng tiếp cận | 10 / 10 |
| Hoàn thiện code | 30 / 30 |
| Dự đoán độ tương tự | 5 / 5 |
| Kết quả truy xuất | 9 / 10 |
| **Tổng phần cá nhân** | **59 / 60** |

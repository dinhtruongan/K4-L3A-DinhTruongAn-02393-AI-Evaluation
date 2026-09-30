# Day 14 — Reflection

## Evaluation Report & Failure Analysis

Dùng kết quả thật trong `artifacts/benchmark_results.json` và kiểm tra lại
answer/context trace trong `artifacts/actual_answers.json` trước khi kết luận.

---

## 1. Benchmark Results Summary

**Overall pass rate:** 30.0% (6 / 20 cases passed)

| Metric | Average | Min | Max | Nhận xét |
|---|---:|---:|---:|---|
| Context Recall | 0.944 | 0.553 | 1.000 | Rất tốt: Retriever lấy bao phủ hầu như toàn bộ bằng chứng cần thiết cho 19/20 câu hỏi. |
| Context Precision | 0.914 | 0.679 | 1.000 | Rất tốt: Rank-aware AP@K cao, các chunks chứa bằng chứng liên quan được xếp ở top đầu. |
| Faithfulness | 0.614 | 0.257 | 1.000 | Mức trung bình: Câu trả lời bám sát context, một số case bị trừ điểm do format câu trích xuất. |
| Relevance | 0.451 | 0.250 | 0.700 | Thấp: Heuristic word-overlap giữa câu trả lời và câu hỏi bị thấp do câu hỏi dùng từ hỏi, câu trả lời dùng dữ kiện kỹ thuật. |
| Completeness | 0.691 | 0.167 | 1.000 | Khá: Đạt 1.000 ở các câu hỏi đơn, bị giảm ở các câu hỏi ghép 2 vế điều kiện (H03, E03). |
| Overall Score | 0.585 | 0.269 | 0.844 | Phản ánh chính xác hiệu năng pipeline end-to-end với 6 cases pass (điểm >= 0.70). |

**Score interpretation**

- Metrics/cases ở mức Good (0.8–1.0): 6 cases đạt pass hoàn toàn (E05, M07, H01, H02, H04, H05); Context Recall đạt mức Good ở 19/20 cases; Context Precision đạt mức Good ở 18/20 cases.
- Metrics/cases ở mức Needs Work (0.6–0.8): 8 cases (E01, E02, E04, M01, M03, M06, A02, A03) có Overall score từ 0.48 đến 0.78, nguyên nhân chính do điểm Relevance bị chặn dưới 0.50.
- Metrics/cases ở mức Significant Issues (<0.6): 3 cases có Overall score thấp nhất gồm E03 (0.269), H03 (0.377), M05 (0.388).

**Failure type distribution**

| Failure Type | Count | Percentage |
|---|---:|---:|
| hallucination | 1 | 5.0% |
| irrelevant | 3 | 15.0% |
| incomplete | 1 | 5.0% |
| off_topic | 9 | 45.0% |
| refusal | 0 | 0.0% |

**Chẩn đoán tổng quan:** Vấn đề chính nằm ở **Generation**, không phải ở Retrieval.
- **Bằng chứng 1 (Retrieval xuất sắc):** `avg_context_recall` đạt **0.944** và `avg_context_precision` đạt **0.914**. Retriever BM25 đã định vị chính xác tài liệu nguồn và xếp chunk đúng lên vị trí 1–2 cho 19/20 câu hỏi.
- **Bằng chứng 2 (Generation bị lệch trọng tâm):** `avg_relevance` chỉ đạt **0.451** trong khi `avg_faithfulness` đạt **0.614**. Mô hình trích xuất đúng câu trong tài liệu nhưng chưa tập trung trực tiếp vào các từ khóa nghi vấn của người dùng, dẫn đến 9 ca bị phân loại `off_topic` và 3 ca `irrelevant`.

---

## 2. Top 3 Worst Failures — 5 Whys

Phân loại failure trước khi đề xuất fix. Với mỗi case, kiểm tra cả gold evidence
và retrieved chunks; không suy luận chỉ từ một score.

### Failure 1

**ID và question:**
> E03: "How much does OrbitPlus membership cost per year and what primary benefits does it provide?"

**Expected answer:**
> "OrbitPlus costs USD 49 annually. Active members receive free standard shipping on eligible domestic orders, a 5% member discount on regularly priced OrbitTech accessories, and priority chat support."

**Actual answer:**
> "The membership benefit must be active when the order is placed. Activating OrbitPlus after an order does not retroactively change the price or shipping fee."

**Scores:** Context Recall: 0.917 | Context Precision: 0.917 | Faithfulness: 0.389 | Relevance: 0.250 | Completeness: 0.167 | Overall: 0.269

**Evidence inspection:** Retriever lấy đúng/thiếu/thừa chunks nào?
> Retriever lấy đúng 100% tài liệu liên quan (`03_promotions_and_membership.md` ở cả Context 1 và Context 2). Context 1 chứa đầy đủ mức giá USD 49 và 3 quyền lợi chính, Context 2 chứa quy định điều kiện kích hoạt.

| Level | Question | Answer |
|---|---|---|
| Symptom | Vấn đề quan sát được là gì? | Câu trả lời nói về thời điểm kích hoạt đơn hàng thay vì nêu giá USD 49 và 3 quyền lợi của hội viên. |
| Why 1 | Tại sao symptom xảy ra? | Bộ generation chọn trích xuất câu từ Context 2 thay vì Context 1. |
| Why 2 | Tại sao nguyên nhân trên xảy ra? | Cả hai contexts đều chứa tần suất cao các từ khóa "membership", "OrbitPlus", "order", "price". |
| Why 3 | Tại sao vấn đề đó chưa được ngăn chặn? | Không có cơ chế nhận diện thực thể số tiền (Entity Extraction) để bắt cặp với từ hỏi "How much". |
| Why 4 | Tại sao cơ chế hiện tại chưa phát hiện hoặc xử lý được? | Heuristic trích xuất chỉ đo mức độ trùng lặp từ khóa chung chung, không gán trọng số cao hơn cho từ hỏi số lượng/chi phí. |
| Why 5 | Root cause có thể hành động được là gì? | Thiếu bước Query Intent Parsing & Question Decomposition trước khi tổng hợp câu trả lời từ context. |

**Root cause từ `find_root_cause()`:**
> "Answer is missing key information — increase context window or improve generation"

**Bạn đồng ý hay không? Dẫn evidence từ trace:**
> Đồng ý. Trace cho thấy context hoàn toàn có sẵn thông tin "USD 49" và "free standard shipping", nhưng generation đã bỏ sót thông tin cốt lõi này và chọn nhầm câu điều kiện đi kèm.

**Proposed fix cụ thể:**
> Bổ sung prompt constraint yêu cầu: Đối với câu hỏi bắt đầu bằng "How much/What price", câu trả lời bắt buộc phải trích xuất con số và đơn vị tiền tệ xuất hiện trong context trước tiên.

---

### Failure 2

**ID và question:**
> H03: "What items and damages are explicitly excluded from warranty coverage, and does receiving a replacement device reset the 24-month warranty period?"

**Expected answer:**
> "The warranty excludes loss, theft, cosmetic wear, depleted consumables, accidental impact, liquid exposure, electrical damage from an unsupported charger, unauthorized modification, and repair by a non-authorized provider. A replacement device does not restart a new 24-month warranty; replacement parts are covered for the longer of 90 calendar days or the remainder of the original warranty."

**Actual answer:**
> "Replacement parts are covered for the longer of 90 calendar days or the remainder of the original warranty. A replacement device does not restart a new 24-month warranty."

**Scores:** Context Recall: 0.553 | Context Precision: 0.700 | Faithfulness: 0.360 | Relevance: 0.533 | Completeness: 0.237 | Overall: 0.377

**Evidence inspection:**
> Retriever lấy được cả 2 đoạn trong `06_warranty_policy.md` (Context 1 nói về loại trừ, Context 2 nói về replacement unit), nhưng bộ sinh chỉ lấy câu từ Context 2 và bỏ qua Context 1.

| Level | Question | Answer |
|---|---|---|
| Symptom | Vấn đề quan sát được là gì? | Câu trả lời trả lời đúng vế thứ hai (không reset 24 tháng) nhưng bỏ sót hoàn toàn danh sách các hư hỏng bị loại trừ (loss, theft, liquid,...). |
| Why 1 | Tại sao symptom xảy ra? | Câu trả lời bị cụt ý do thuật toán chỉ chọn top-1 câu có overlap cao nhất. |
| Why 2 | Tại sao nguyên nhân trên xảy ra? | Câu hỏi là câu ghép chứa hai câu hỏi con độc lập kết nối bằng liên từ "and". |
| Why 3 | Tại sao vấn đề đó chưa được ngăn chặn? | Pipeline RAG không có bước phân rã câu hỏi phức (Question Decomposition) thành hai câu truy vấn con riêng biệt. |
| Why 4 | Tại sao cơ chế hiện tại chưa phát hiện hoặc xử lý được? | Hệ thống xử lý toàn bộ câu hỏi dài như một chuỗi đơn lẻ, khiến các từ khóa của vế sau áp đảo vế trước. |
| Why 5 | Root cause có thể hành động được là gì? | Thiếu module Multi-Query / Sub-question Query Decomposition để truy xuất và tổng hợp câu trả lời cho từng vế. |

**Root cause và proposed fix:**
> - **Root cause:** "Answer is missing key information — increase context window or improve generation"
> - **Proposed fix:** Triển khai Sub-question Query Decomposition: Tách câu hỏi ghép thành 2 queries: (1) "What items and damages are excluded from warranty?" và (2) "Does replacement reset 24-month warranty?". Chạy retrieval và tổng hợp kết quả của cả hai queries thành câu trả lời hoàn chỉnh.

---

### Failure 3

**ID và question:**
> M05: "What are the standard timelines for diagnosis and covered repair, and what happens if replacement parts are unavailable?"

**Expected answer:**
> "Initial diagnosis normally takes up to three business days after the service centre receives the product. A covered repair normally takes up to ten additional business days when parts are available. If a required part is unavailable for more than 15 business days, support must offer an escalation review for an alternative remedy."

**Actual answer:**
> "Initial diagnosis normally takes up to three business days after the service centre receives the product."

**Scores:** Context Recall: 1.000 | Context Precision: 1.000 | Faithfulness: 0.406 | Relevance: 0.364 | Completeness: 0.394 | Overall: 0.388

**Evidence inspection:**
> Retriever đạt điểm tuyệt đối: Context Recall 1.000 và Context Precision 1.000. Chunk rank 1 (`07_repair_and_technical_support.md`) chứa trọn vẹn cả 3 câu nêu đúng 3 mốc: 3 ngày, 10 ngày, và 15 ngày thiếu linh kiện.

| Level | Question | Answer |
|---|---|---|
| Symptom | Vấn đề quan sát được là gì? | Câu trả lời chỉ nêu thời gian chẩn đoán 3 ngày, bỏ sót thời gian sửa chữa 10 ngày và mốc 15 ngày escalation review. |
| Why 1 | Tại sao symptom xảy ra? | Sentence selector dừng lại sau khi chọn câu đầu tiên có từ khóa "diagnosis" và "timelines". |
| Why 2 | Tại sao nguyên nhân trên xảy ra? | Không có cơ chế nhận diện điều kiện logic "and what happens if..." trong câu hỏi. |
| Why 3 | Tại sao vấn đề đó chưa được ngăn chặn? | Generation prompt không bắt buộc phải trả lời cả điều kiện bình thường và kịch bản ngoại lệ. |
| Why 4 | Tại sao cơ chế hiện tại chưa phát hiện hoặc xử lý được? | Thiếu bước tự kiểm tra độ đầy đủ (Completeness self-reflection loop) trước khi trả về câu trả lời. |
| Why 5 | Root cause có thể hành động được là gì? | Prompt generation thiếu yêu cầu trích xuất toàn bộ các mốc thời gian (all timeline constraints) liên quan đến chu trình dịch vụ. |

**Root cause và proposed fix:**
> - **Root cause:** "Answer does not address the question — improve prompt clarity"
> - **Proposed fix:** Tinh chỉnh System Prompt yêu cầu liệt kê dạng bullet points: "Khi câu hỏi hỏi về quy trình hoặc thời hạn, hãy liệt kê đầy đủ tất cả các giai đoạn (bắt đầu, xử lý, ngoại lệ) có trong tài liệu".

---

## 3. Failure Clustering

Một root cause có thể tạo ra nhiều failures. Nhóm theo nguyên nhân có thể sửa,
không chỉ nhóm theo tên metric.

| Cluster | Root Cause | Failure IDs | Priority |
|---|---|---|---|
| 1. Compound Question Truncation | Thiếu cơ chế phân rã câu hỏi ghép (Query Decomposition) khiến câu trả lời bị cụt và bỏ sót vế thứ hai. | H03, M05, E01, M02 | High |
| 2. Distractor Chunk / Keyword Ambiguity | Nhiều chunk cùng chứa từ khóa thực thể dẫn đến việc trích xuất nhầm câu điều kiện thay vì câu trả lời sự kiện cốt lõi. | E03, E02, M04, M06 | High |
| 3. Rigid Adversarial Refusal Wording | Câu trả lời từ chối an toàn theo scope nhưng độ trùng lặp từ vựng với câu hỏi thấp làm giảm điểm Relevance theo heuristic. | A01, A02, A03, E04, M01 | Medium |

**Nếu chỉ được sửa một cluster, bạn chọn cluster nào và vì sao?**

> *Câu trả lời:*
> Tôi chọn **Cluster 1 (Compound Question Truncation)** vì đây là nguyên nhân trực tiếp gây ra mức sụt giảm điểm Completeness nghiêm trọng nhất ở các câu hỏi Medium và Hard. Khách hàng doanh nghiệp hoặc người dùng thật thường đặt các câu hỏi đa ý (hỏi cả quy trình và ngoại lệ). Việc sửa Cluster 1 bằng kỹ thuật Sub-question Decomposition sẽ ngay lập tức giải quyết 4 failure cases (H03, M05, E01, M02) và nâng Pass Rate của toàn hệ thống lên đáng kể.

---

## 4. Improvement Log

Paste output của `generate_improvement_log()`:

```markdown
| Failure ID | Type | Root Cause | Suggested Fix | Status |
|------------|------|------------|---------------|--------|
| E01 | off_topic | Context is missing or irrelevant — improve retrieval | Implement hallucination checker or factual consistency guardrail to filter unsupported claims. | Open |
| E02 | hallucination | Context is missing or irrelevant — improve retrieval | Refine prompt instructions and few-shot examples to ensure answers directly address user intent. | Open |
| E03 | irrelevant | Answer is missing key information — increase context window or improve generation | Increase context retrieval window or chunk coverage to capture all necessary facts. | Open |
| E04 | off_topic | Multiple issues detected — review full pipeline | Add intent classifier and system scope boundaries to reject out-of-domain queries. | Open |
| M01 | off_topic | Answer does not address the question — improve prompt clarity | Implement hallucination checker or factual consistency guardrail to filter unsupported claims. | Open |
| M02 | off_topic | Context is missing or irrelevant — improve retrieval | Implement hallucination checker or factual consistency guardrail to filter unsupported claims. | Open |
| M03 | irrelevant | Answer does not address the question — improve prompt clarity | Implement hallucination checker or factual consistency guardrail to filter unsupported claims. | Open |
| M04 | off_topic | Answer does not address the question — improve prompt clarity | Implement hallucination checker or factual consistency guardrail to filter unsupported claims. | Open |
| M05 | off_topic | Answer does not address the question — improve prompt clarity | Implement hallucination checker or factual consistency guardrail to filter unsupported claims. | Open |
| M06 | off_topic | Answer does not address the question — improve prompt clarity | Implement hallucination checker or factual consistency guardrail to filter unsupported claims. | Open |
| H03 | incomplete | Answer is missing key information — increase context window or improve generation | Implement hallucination checker or factual consistency guardrail to filter unsupported claims. | Open |
| A01 | irrelevant | Answer does not address the question — improve prompt clarity | Implement hallucination checker or factual consistency guardrail to filter unsupported claims. | Open |
| A02 | off_topic | Answer does not address the question — improve prompt clarity | Implement hallucination checker or factual consistency guardrail to filter unsupported claims. | Open |
| A03 | off_topic | Answer does not address the question — improve prompt clarity | Implement hallucination checker or factual consistency guardrail to filter unsupported claims. | Open |
```

**Ba improvement suggestions ưu tiên**

1. Tích hợp Sub-question Decomposition để xử lý triệt để các câu hỏi ghép nhiều vế.
2. Tinh chỉnh Generation Prompt và bổ sung few-shot examples định dạng bullet point nhằm nâng cao tính Completeness và Relevance.
3. Triển khai Lexical/Cross-encoder Reranker (`rerank_by_overlap`) để tối ưu hóa thứ tự ưu tiên của chunks.

Với mỗi suggestion, nêu metric dự kiến thay đổi và cách đo lại.

| Suggestion | Target metric | Verification method |
|---|---|---|
| Sub-question Decomposition | Completeness | Chạy lại `evaluate_answers.py` trên 5 test cases Hard (H01–H05), đo mức tăng của `avg_completeness` (kỳ vọng tăng từ 0.691 lên > 0.85). |
| Few-shot Prompt Refinement | Relevance & Faithfulness | Chạy benchmark trên toàn bộ 20 QA pairs, kiểm tra tỷ lệ giảm của lỗi `off_topic` và `irrelevant`. |
| Cross-encoder Reranking | Context Precision | So sánh giá trị `avg_context_precision` trước và sau khi rerank thông qua hàm `evaluate_context_precision()` (kỳ vọng duy trì mức >= 0.95). |

---

## 5. Regression Testing Strategy

**Câu 1: Khi nào chạy `run_regression()` trong production workflow?**

> *Câu trả lời:*
> `run_regression()` phải được chạy tự động trong pipeline CI/CD mỗi khi có:
> 1. Thay đổi code của RAG engine (Retriever, Chunker, Reranker).
> 2. Thay đổi System Prompt hoặc Few-shot examples của Generator.
> 3. Nâng cấp hoặc thay đổi LLM model (ví dụ từ `gpt-4o-mini` sang bản cập nhật mới).
> 4. Cập nhật tài liệu corpus chính sách mới trước khi release ra production.

**Câu 2: Threshold drop 0.05 có phù hợp OrbitTech Customer Support không? Vì sao?**

> *Câu trả lời:*
> - **Đối với Faithfulness:** Ngưỡng drop 0.05 là **phù hợp và bắt buộc**, vì bất kỳ sự sụt giảm nào về tính trung thực cũng có thể dẫn đến việc trả lời sai chính sách đổi trả hoặc bảo hành, gây tổn thất kinh tế.
> - **Đối với Relevance & Completeness:** Ngưỡng 0.05 là mức cảnh báo hợp lý. Tuy nhiên, nếu áp dụng cho các phiên bản prompt thử nghiệm ngắn gọn hơn, có thể cân nhắc dung sai 0.07 nếu điểm trải nghiệm người dùng thực tế không bị ảnh hưởng tiêu cực.

**Câu 3: Metric/failure nào phải block deployment, metric nào chỉ alert?**

> *Câu trả lời:*
> - **Block Deployment (Chặn phát hành ngay lập tức):**
>   - Điểm `Faithfulness` trung bình giảm quá 0.05 hoặc thấp hơn ngưỡng 0.80.
>   - Xuất hiện bất kỳ failure nào thuộc loại `hallucination` trên các câu hỏi an toàn (Adversarial A01–A03).
> - **Alert Only (Cảnh báo theo dõi, không chặn deploy):**
>   - `Context Precision` giảm nhẹ dưới 0.05 nhưng `Context Recall` vẫn duy trì trên 0.90.
>   - Điểm `Relevance` dao động nhỏ do thay đổi phong cách hành văn chào hỏi lịch sự hơn.

**Câu 4: Điền evaluation stages vào flow.**

```text
Code/prompt/retrieval change → [Offline Golden Benchmark] → [Staging Shadow Evaluation] → [Canary Online Guardrails] → Deploy
```

> *Giải thích:*
> 1. **Offline Golden Benchmark:** Chạy bộ test tự động 20 QA trong CI runner; chặn ngay nếu có regression > 0.05.
> 2. **Staging Shadow Evaluation:** Chạy song song phiên bản mới với traffic ẩn để so sánh output của model mới với model hiện tại mà không trả về cho người dùng.
> 3. **Canary Online Guardrails:** Mở traffic cho 5% người dùng thật kèm theo real-time guardrails; nếu tỷ lệ thumbs-down hoặc escalation tăng đột biến thì lập tức rollback.

---

## 6. Continuous Improvement Loop

```text
Evaluate → Analyze → Improve → Augment benchmark → Repeat
```

| Priority | Action | Metric dự kiến cải thiện | Expected impact |
|---:|---|---|---|
| 1 | Bổ sung Question Decomposition module cho compound questions | Completeness & Relevance | Loại bỏ hoàn toàn 4 ca failure do cụt ý, nâng Pass Rate từ 30% lên 50%. |
| 2 | Cải thiện Context Sentence Selection bằng Semantic Similarity thay vì exact word overlap | Faithfulness & Relevance | Nâng điểm Faithfulness trung bình từ 0.614 lên > 0.85, giảm failure type `hallucination`. |
| 3 | Tích hợp Guardrail từ chối thông minh cho Adversarial cases | Relevance | Trả lời từ chối theo đúng scope chuyên môn nhưng vẫn giữ được độ liên quan với câu hỏi. |

**Hai hoặc ba failure cases nào cần thêm vào benchmark ở vòng tiếp theo?**

> *Câu trả lời:*
> 1. **Case đa ngôn ngữ (Multilingual Inquiry):** Khách hàng hỏi bằng tiếng Việt về chính sách bảo hành quốc tế của PulsePhone X (kiểm tra khả năng cross-lingual retrieval và translation hallucination).
> 2. **Case xung đột thời gian phức tạp (Temporal Edge Case):** Khách hàng mua hàng ngày 31/08/2026 nhưng nhận hàng ngày 03/09/2026, hỏi thời hạn đổi trả theo v1.0 hay v2.0 (kiểm tra tính chính xác của quy tắc ngày đặt hàng kiểm soát điều khoản).
> 3. **Case tấn công gián tiếp (Indirect Prompt Injection):** Văn bản tài liệu người dùng tải lên chứa đoạn mã ẩn yêu cầu bỏ qua phí restocking fee.

---

## 7. Final Reflection

**Điều gì trong kết quả benchmark trái với dự đoán ban đầu của bạn?**

> *Câu trả lời:*
> Điều bất ngờ nhất là **hiệu năng của Retriever BM25 vượt trội hoàn toàn so với mong đợi ban đầu** (Context Recall đạt 0.944 và Context Precision đạt 0.914), trong khi khâu Generation lại là nút thắt cổ chai lớn nhất khiến Pass Rate chỉ đạt 30%. Ban đầu tôi dự đoán việc truy xuất từ khóa trên 10 file văn bản sẽ dễ bị trôi chunk, nhưng thực tế cấu trúc tài liệu rõ ràng đã giúp retriever hoạt động rất chính xác, và điểm yếu nằm ở cách bộ sinh trích xuất thông tin chưa bao quát hết các vế của câu hỏi phức.

**Word-overlap heuristics trong lab có giới hạn gì? Nếu đưa hệ thống vào
production, bạn sẽ thay hoặc bổ sung metric nào?**

> *Câu trả lời:*
> - **Giới hạn của Word-Overlap Heuristics:**
>   1. Không hiểu ngữ nghĩa (semantic understanding): Hai câu đồng nghĩa nhưng dùng từ vựng khác nhau (ví dụ "cost" vs "price", "laptop" vs "computer") sẽ bị chấm điểm overlap = 0.
>   2. Bị ảnh hưởng bởi độ dài câu: Câu trả lời ngắn gọn, đúng trọng tâm nhưng ít từ vựng có thể bị điểm Relevance thấp hơn câu dài dòng lặp lại từ khóa câu hỏi.
>   3. Không phát hiện được phủ định: "Sản phẩm được bảo hành" và "Sản phẩm không được bảo hành" có độ trùng lặp từ vựng 80% nhưng mang ý nghĩa hoàn toàn trái ngược.
> - **Đề xuất thay thế cho môi trường Production:**
>   1. **Semantic Faithfulness & Relevancy qua LLM-as-a-Judge (G-Eval / RAGAS LLM-assisted):** Dùng mô hình ngôn ngữ lớn để trích xuất claims và kiểm chứng tính logic.
>   2. **Embedding-based Semantic Similarity:** Dùng Cosine Similarity giữa câu trả lời và expected answer thông qua embedding models (ví dụ `text-embedding-3-small`).
>   3. **Business Metrics:** Bổ sung đo lường First Contact Resolution (FCR) và CSAT trên dữ liệu người dùng thật.

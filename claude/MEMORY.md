# Project Memory: Bank OCR Automation

## Project Overview
Software for banks to automate account creation, reducing manual entry for CSOs and review time for branch managers.

## Workflow
1. **Input**: CSO scans CNI (ID card) and Location Plan.
2. **Processing**: 
   - Extraction of text from images.
   - Structuring of text into specific fields via LLM (Mistral).
3. **Completion**:
   - CSO fills remaining missing information via a web form.
   - Recap page is displayed and printed for the client.
4. **Account Setup**:
   - Selection of account type $\rightarrow$ Mandatory/Optional products.
   - Finalization of account creation.
5. **Integration & Tracking**:
   - Copy buttons for fields to paste into 'Amplitude' software.
   - LocalStorage for daily tracking of created accounts (resets at midnight).

## Current Technical Stack
- **OCR CNI**: EasyOCR (Working).
- **OCR Plan (Handwritten)**: Transitioning from [EasyOCR $\rightarrow$ TrOCR $\rightarrow$ Mistral] to **LLaVA (via Ollama)**.
- **Structuring**: Mistral LLM (via Ollama).
- **Storage**: LocalStorage.
- **Frontend**: Web-based.

## User Preferences & Constraints
- **Strict Indentation**: All code provided must strictly respect Python alignment and indentation rules to avoid `IndentationError`. No accidental spaces at the start of top-level lines.
- **Cost**: Solutions must be free/open-source for long-term bank deployment.
- **Confidentiality**: 100% local processing required (no external cloud APIs for sensitive bank documents).

## Project History & Technical Journey
- **Initial phase**: Implemented EasyOCR for CNI (Success).
- **Handwritten Plan struggles**: 
    - Attempted EasyOCR $\rightarrow$ Failed (cannot read handwriting).
    - Attempted Moondream $\rightarrow$ Failed (no extraction).
    - Attempted Donut $\rightarrow$ Failed (hallucinations/infinite loops of characters).
- **The "Frankenstein" Pipeline**: Tried a modular approach [EasyOCR Detection $\rightarrow$ TrOCR Recognition $\rightarrow$ Mistral Structuring]. Result: Better than Donut, but still too many errors for bank-grade quality.
- **Insight from Unstract**: Analyzed Unstract's success (LLMWhisperer). Realized that "Parsing" is different from "OCR" and that cloud-based parsing is the gold standard but prohibited by bank security.
- **Current Pivot**: Moving to **LLaVA via Ollama**. Shifting from a sequential pipeline to a Vision-Language Model (VLM) for holistic image understanding.

## Current Blockers
- Validating the extraction accuracy of handwritten location plans using LLaVA.

## Future Improvements / Professional Roadmap
- **Reliability**: Implement confidence scores (color-coded fields) and cross-model verification for critical data.
- **Security**: Move to in-memory processing (RAM), implement audit trails for CSO modifications, and add API authentication.
- **UX**: Side-by-side view (Image vs Form) and asynchronous processing (background loading) to prevent UI freezing.
- **Architecture**: Introduce a task queue (e.g., Celery/Redis) to handle concurrent requests and use quantized models (4-bit/8-bit) for better RAM efficiency.

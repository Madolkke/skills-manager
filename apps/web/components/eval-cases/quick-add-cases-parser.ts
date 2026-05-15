export type QuickEvalCaseDraft = {
  title: string;
  input_text: string;
  expected_output: string;
  notes?: string;
};
export type BatchCaseRowError = {
  lineNumber: number;
  message: string;
};

export type BatchCasePreviewRow = QuickEvalCaseDraft & {
  lineNumber: number;
  status: "valid" | "invalid";
  message?: string;
};

export type BatchCaseParseResult = {
  valid: QuickEvalCaseDraft[];
  invalidRows: BatchCaseRowError[];
  invalidCount: number;
  previewRows: BatchCasePreviewRow[];
};

const FIELD_LABELS = {
  title: "标题",
  input_text: "Input",
  expected_output: "Expected output",
};

export function parseBatchCases(text: string): BatchCaseParseResult {
  const valid: QuickEvalCaseDraft[] = [];
  const invalidRows: BatchCaseRowError[] = [];
  const previewRows: BatchCasePreviewRow[] = [];

  text.split(/\r?\n/).forEach((line, index) => {
    const row = line.trim();
    if (!row) return;

    const separator = row.includes("\t") ? "\t" : "|";
    const [title, inputText, expectedOutput, notes] = row.split(separator).map((part) => part.trim());
    const missing = missingFields({ title, input_text: inputText, expected_output: expectedOutput });

    if (missing.length > 0) {
      const message = rowErrorMessage(index + 1, missing);
      invalidRows.push({ lineNumber: index + 1, message });
      previewRows.push(previewRow(index + 1, "invalid", title, inputText, expectedOutput, notes, message));
      return;
    }

    const draft = {
      title,
      input_text: inputText,
      expected_output: expectedOutput,
      notes: notes || undefined,
    };
    valid.push(draft);
    previewRows.push(previewRow(index + 1, "valid", title, inputText, expectedOutput, notes));
  });

  return { valid, invalidRows, invalidCount: invalidRows.length, previewRows };
}

export function batchCaseErrorMessage(invalidRows: BatchCaseRowError[]) {
  const visibleRows = invalidRows.slice(0, 3).map((row) => row.message).join(" ");
  const hiddenCount = invalidRows.length - 3;
  return hiddenCount > 0 ? `${visibleRows} 还有 ${hiddenCount} 行需要修正。` : visibleRows;
}

function missingFields(fields: Record<keyof typeof FIELD_LABELS, string | undefined>) {
  return Object.entries(fields)
    .filter(([, value]) => !value)
    .map(([field]) => FIELD_LABELS[field as keyof typeof FIELD_LABELS]);
}

function rowErrorMessage(lineNumber: number, missing: string[]) {
  const fieldList = missing.length === 1 ? missing[0] : missing.join("、");
  const separator = /^[A-Za-z]/.test(fieldList) ? " " : "";
  return `第 ${lineNumber} 行缺少${separator}${fieldList}。`;
}

function previewRow(
  lineNumber: number,
  status: BatchCasePreviewRow["status"],
  title = "",
  inputText = "",
  expectedOutput = "",
  notes = "",
  message?: string,
): BatchCasePreviewRow {
  return {
    lineNumber,
    status,
    title,
    input_text: inputText,
    expected_output: expectedOutput,
    ...(notes ? { notes } : {}),
    ...(message ? { message } : {}),
  };
}

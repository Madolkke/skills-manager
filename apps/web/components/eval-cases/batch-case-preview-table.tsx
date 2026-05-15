import type { BatchCasePreviewRow } from "@/components/eval-cases/quick-add-cases-parser";

export function BatchCasePreviewTable({ rows }: { rows: BatchCasePreviewRow[] }) {
  if (rows.length === 0) {
    return (
      <div className="quickCaseBatchEmpty">
        <strong>等待预览</strong>
        <span>尚未检测到可预览行。</span>
      </div>
    );
  }

  return (
    <div className="quickCaseBatchTableFrame">
      <table className="quickCaseBatchTable">
        <caption>批量 case 导入预览</caption>
        <thead>
          <tr>
            <th scope="col">行</th>
            <th scope="col">状态</th>
            <th scope="col">标题</th>
            <th scope="col">Input</th>
            <th scope="col">Expected output</th>
            <th scope="col">Notes</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((row) => (
            <tr className={row.status === "invalid" ? "quickCaseBatchRowInvalid" : ""} key={row.lineNumber}>
              <th scope="row">{row.lineNumber}</th>
              <td>
                <span className={`quickCaseBatchStatus quickCaseBatchStatus-${row.status}`}>
                  {row.status === "valid" ? "可导入" : "需修正"}
                </span>
                {row.message ? <small>{row.message}</small> : null}
              </td>
              <PreviewCell value={row.title} />
              <PreviewCell value={row.input_text} />
              <PreviewCell value={row.expected_output} />
              <PreviewCell value={row.notes} />
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function PreviewCell({ value }: { value?: string }) {
  return <td>{value ? <span title={value}>{value}</span> : <em>-</em>}</td>;
}

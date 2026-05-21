import { FileArchive, FolderOpen } from "lucide-react";
import { useRef, useState } from "react";

type BundlePickerProps = {
  onFiles: (folderFiles: File[], zipFile: File | null) => void;
};

export function BundlePicker({ onFiles }: BundlePickerProps) {
  const folderRef = useRef<HTMLInputElement | null>(null);
  const zipRef = useRef<HTMLInputElement | null>(null);
  const [label, setLabel] = useState("尚未选择 bundle");

  function acceptFolder(files: FileList | null) {
    const folderFiles = files ? Array.from(files) : [];
    setLabel(folderFiles.length ? `${folderFiles[0]?.webkitRelativePath?.split("/")[0] ?? "bundle"} · ${folderFiles.length} files` : "尚未选择 bundle");
    onFiles(folderFiles, null);
  }

  function acceptZip(files: FileList | null) {
    const zip = files?.[0] ?? null;
    setLabel(zip ? `${zip.name} · zip` : "尚未选择 bundle");
    onFiles([], zip);
  }

  return (
    <div className="bundle-picker">
      <input
        ref={folderRef}
        name="folder_files"
        type="file"
        multiple
        className="hidden-input"
        onChange={(event) => acceptFolder(event.target.files)}
        {...{ webkitdirectory: "", directory: "" }}
      />
      <input ref={zipRef} name="zip_file" type="file" accept=".zip" className="hidden-input" onChange={(event) => acceptZip(event.target.files)} />
      <button className="picker-tile" type="button" onClick={() => folderRef.current?.click()}>
        <FolderOpen size={24} />
        <span>选择文件夹</span>
      </button>
      <button className="picker-tile" type="button" onClick={() => zipRef.current?.click()}>
        <FileArchive size={24} />
        <span>上传 zip</span>
      </button>
      <div className="picker-label">{label}</div>
    </div>
  );
}

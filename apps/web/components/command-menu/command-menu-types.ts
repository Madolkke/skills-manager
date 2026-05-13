export type CommandMenuPreview = {
  body: string;
  facts?: Array<{ label: string; value: string }>;
  title?: string;
};

export type CommandMenuItem = {
  id: string;
  title: string;
  group: string;
  detail: string;
  shortcut?: string;
  disabled?: boolean;
  disabledReason?: string;
  preview?: CommandMenuPreview;
  run: () => void;
};

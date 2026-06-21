export type DropdownSelectOption = {
  value: string;
  label: string;
  description?: string;
  disabled?: boolean;
};

export type DropdownSelectGroup = {
  label?: string;
  options: DropdownSelectOption[];
};

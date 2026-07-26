export default function Switch({
  checked,
  onChange,
  disabled,
}: {
  checked: boolean;
  onChange: (value: boolean) => void;
  disabled?: boolean;
}) {
  return (
    <span className="switch">
      <input
        type="checkbox"
        checked={checked}
        disabled={disabled}
        onChange={(event) => onChange(event.target.checked)}
        id={undefined}
      />
      <span
        className="track"
        onClick={() => {
          if (!disabled) onChange(!checked);
        }}
      />
    </span>
  );
}

type NoticeProps = {
  message: string;
  isError?: boolean;
};

export function Notice({ message, isError = false }: NoticeProps) {
  return <section className={`notice ${isError ? "error" : ""}`}>{message}</section>;
}

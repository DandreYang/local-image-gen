export function PageAlert({ message }) {
  return message ? <div className="page-alert" role="alert">{message}</div> : null;
}

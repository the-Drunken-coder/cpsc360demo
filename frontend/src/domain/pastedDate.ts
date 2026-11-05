export function parsePastedDate(text: string): string | undefined {
  const input = text.trim();
  const monthFirst = input.includes("/");
  const parts = input.split(monthFirst ? "/" : "-");
  const [first, second, third] = parts;
  if (parts.length !== 3 || first === undefined || second === undefined || third === undefined) return undefined;

  const year = monthFirst ? third : first;
  const month = monthFirst ? first : second;
  const day = monthFirst ? second : third;
  if (!/^\d{4}$/.test(year) || Number(year) === 0 || !/^\d{1,2}$/.test(month) || !/^\d{1,2}$/.test(day)) return undefined;

  const value = `${year}-${month.padStart(2, "0")}-${day.padStart(2, "0")}`;
  const date = new Date(`${value}T00:00:00Z`);
  return !Number.isNaN(date.getTime()) && date.toISOString().slice(0, 10) === value ? value : undefined;
}

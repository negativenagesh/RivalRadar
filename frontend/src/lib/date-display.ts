/** ISO YYYY-MM-DD <-> dd/mm/yyyy for the Custom lookback chip. */

const ISO = /^(\d{4})-(\d{2})-(\d{2})$/;
const DMY = /^(\d{1,2})\/(\d{1,2})\/(\d{4})$/;

export function isoToDmy(iso: string | null | undefined): string {
  if (!iso) return "";
  const m = ISO.exec(iso.trim());
  if (!m) return "";
  return `${m[3]}/${m[2]}/${m[1]}`;
}

export function showCustomDateFields(
  customOpen: boolean,
  dateFrom?: string | null,
  dateTo?: string | null,
): boolean {
  return customOpen || Boolean(dateFrom || dateTo);
}

export function dmyToIso(dmy: string | null | undefined): string | null {
  if (!dmy) return null;
  const m = DMY.exec(dmy.trim());
  if (!m) return null;
  const dd = Number(m[1]);
  const mm = Number(m[2]);
  const yyyy = Number(m[3]);
  if (mm < 1 || mm > 12 || dd < 1 || dd > 31 || yyyy < 2000 || yyyy > 2100) return null;
  const dt = new Date(Date.UTC(yyyy, mm - 1, dd));
  if (dt.getUTCFullYear() !== yyyy || dt.getUTCMonth() !== mm - 1 || dt.getUTCDate() !== dd) {
    return null;
  }
  return `${yyyy}-${String(mm).padStart(2, "0")}-${String(dd).padStart(2, "0")}`;
}

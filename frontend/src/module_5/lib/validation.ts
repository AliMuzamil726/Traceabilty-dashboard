/** Client checks for the Schedule dialog. The server repeats every one of them. */

export interface TransportValues {
  site_id: string;
  scheduled_date: string;
  driver_name: string;
  driver_phone: string;
  vehicle_no: string;
}

const PK_MOBILE = /^(?:\+92|0092|0)?3\d{9}$/;
const UK_MOBILE = /^(?:\+44|0044|0)?7\d{9}$/;
const VEHICLE = /^[A-Z0-9][A-Z0-9 -]{1,18}[A-Z0-9]$/;

export function validateTransport(v: TransportValues, country: string | undefined, today: string): Record<string, string> {
  const errors: Record<string, string> = {};
  if (!v.site_id) errors.site_id = 'Choose where the crop goes.';
  if (!v.scheduled_date) errors.scheduled_date = 'Choose a date.';
  else if (v.scheduled_date < today) errors.scheduled_date = 'Choose today or a later date.';
  if (v.driver_name.trim().length < 2) errors.driver_name = "Enter the driver's name.";
  const phone = v.driver_phone.replace(/[\s\-()]/g, '');
  if (!phone) errors.driver_phone = "Enter the driver's phone.";
  else if (country === 'PK' && !PK_MOBILE.test(phone)) errors.driver_phone = 'Enter a Pakistani mobile number, for example 0300 1234567.';
  else if (country === 'GB' && !UK_MOBILE.test(phone)) errors.driver_phone = 'Enter a UK mobile number, for example 07700 900123.';
  const vehicle = v.vehicle_no.trim().toUpperCase().replace(/\s+/g, ' ');
  if (!VEHICLE.test(vehicle)) errors.vehicle_no = 'Enter the vehicle number, 3 to 20 letters, digits, spaces or hyphens.';
  return errors;
}

export function todayIso(): string {
  const d = new Date();
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`;
}

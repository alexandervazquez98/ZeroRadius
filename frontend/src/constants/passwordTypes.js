// Password check types an operator can choose for a RADIUS user.
// The backend hashes MD5-Password and NT-Password on write and never returns
// password values.
export const PASSWORD_TYPES = ['Cleartext-Password', 'MD5-Password', 'NT-Password'];

// Which authentication protocols each stored format can satisfy (#96).
export const PASSWORD_TYPE_HELP = {
    'Cleartext-Password': 'Cleartext-Password works with PAP, CHAP and MS-CHAPv2, but stores the password in cleartext.',
    'MD5-Password': 'MD5-Password works with PAP only (e.g. Cisco IOS, Moxa). MS-CHAPv2 devices such as MikroTik reject it.',
    'NT-Password': 'NT-Password works with PAP and MS-CHAPv2 (e.g. Cisco IOS and MikroTik). Unsalted hash: avoids cleartext storage but is not strong protection.',
};

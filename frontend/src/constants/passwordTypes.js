// Password check types an operator can choose for a RADIUS user.
// The backend hashes MD5-Password on write and never returns password values.
export const PASSWORD_TYPES = ['Cleartext-Password', 'MD5-Password'];

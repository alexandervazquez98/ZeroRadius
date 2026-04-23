import bcrypt
hash_val = b'$2b$12$NI9wi2f0g1mIHdT6LpRlluHZQ.6JL6iCpRoB/LUDABFuDsofrR4Sq'
print("admin", bcrypt.checkpw(b'admin', hash_val))
print("123456", bcrypt.checkpw(b'123456', hash_val))
print("password", bcrypt.checkpw(b'password', hash_val))
print("admin123", bcrypt.checkpw(b'admin123', hash_val))

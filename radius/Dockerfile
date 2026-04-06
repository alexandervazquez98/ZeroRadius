FROM freeradius/freeradius-server:3.2.3

# Install netcat for MySQL health checks (Debian-based image, not Alpine)
RUN apt-get update && apt-get install -y --no-install-recommends netcat-openbsd && rm -rf /var/lib/apt/lists/*

# Enable SQL module by linking
RUN cd /etc/raddb/mods-enabled && \
    ln -s ../mods-available/sql sql

# Configure SQL to use MySQL/MariaDB
# We replace the entire sql config file content with a simplified version that uses env vars

# Configure SQL to use MySQL/MariaDB
# We expect the container to pick up env vars automatically for the standard sql module
# or we will mount a correct config if needed. But for now, let's trust the default module config structure
# which reads env vars.

# Enable read_clients in SQL module
# Also FIX THE DRIVER which defaults to rlm_sql_null
# AND disable TLS ca_file check which fails (we don't use TLS for local docker db)
# AND hardcode connection params because env vars seem flaky in this context
RUN sed -i 's/driver = "rlm_sql_null"/driver = "rlm_sql_mysql"/g' /etc/raddb/mods-available/sql && \
    sed -i 's/#\s*read_clients = yes/read_clients = yes/g' /etc/raddb/mods-available/sql && \
    sed -i 's/#\s*client_table = "nas"/client_table = "nas"/g' /etc/raddb/mods-available/sql && \
    sed -i 's/ca_file = "/# ca_file = "/g' /etc/raddb/mods-available/sql && \
    sed -i 's/certificate_file = "/# certificate_file = "/g' /etc/raddb/mods-available/sql && \
    sed -i 's/private_key_file = "/# private_key_file = "/g' /etc/raddb/mods-available/sql && \
    sed -i 's/tls_required = yes/tls_required = no/g' /etc/raddb/mods-available/sql && \
    sed -i 's/#\s*server = .*/server = "$ENV{DB_HOST}"/g' /etc/raddb/mods-available/sql && \
    sed -i 's/#\s*port = .*/port = "3306"/g' /etc/raddb/mods-available/sql && \
    sed -i 's/#\s*login = .*/login = "radius"/g' /etc/raddb/mods-available/sql && \
    sed -i 's/#\s*password = .*/password = "secure_radius_password"/g' /etc/raddb/mods-available/sql && \
    sed -i 's/#\s*radius_db = .*/radius_db = "radius"/g' /etc/raddb/mods-available/sql && \
    sed -i 's/min = .*/min = 1/g' /etc/raddb/mods-available/sql && \
    sed -i 's/spare = .*/spare = 1/g' /etc/raddb/mods-available/sql && \
    sed -i 's/start = .*/start = 1/g' /etc/raddb/mods-available/sql && \
    sed -i 's/idle_timeout = .*/idle_timeout = 0/g' /etc/raddb/mods-available/sql && \
    sed -i 's/authorize_group_reply_query = "SELECT id, groupname, attribute, value, op FROM/authorize_group_reply_query = "SELECT id, groupname, attribute, CAST(value AS CHAR) AS value, op FROM/g' /etc/raddb/mods-available/sql

# Enable linelog module (custom config)
# linelog is referenced in radius/default.conf (bind-mounted), so we just
# need the module available inside the image.
COPY linelog /etc/raddb/mods-available/linelog
RUN cd /etc/raddb/mods-enabled && \
    ln -sf ../mods-available/linelog linelog

# Install Cambium Dictionary - AUTOMATED METHOD
# We create a directory for custom dictionaries and tell FreeRADIUS to include our helper file
RUN mkdir -p /etc/raddb/custom_dictionaries && \
    echo '$INCLUDE /etc/raddb/custom_dictionaries/Cambium_450i' >> /etc/raddb/dictionary

# Remove conflict with default Motorola dictionary (Attribute 50 collision)
RUN sed -i 's/\$INCLUDE dictionary.motorola.wimax/# $INCLUDE dictionary.motorola.wimax/g' /usr/share/freeradius/dictionary.motorola

# Enable EAP-TTLS
# CRITICAL: For EAP-TTLS to return SQL attributes (like Cambium-Canopy-UserLevel),
# we MUST enable use_tunneled_reply = yes.
RUN sed -i 's/use_tunneled_reply = no/use_tunneled_reply = yes/g' /etc/raddb/mods-available/eap

# Note: default_eap_type for TTLS should NOT be changed here
# The inner authentication method (PAP vs MD5) is configured inside the TTLS section
# Keep as md5 - this is the outer EAP type default, not the inner TTLS method
# (Default is md5, so no sed needed)

# ============================================================================
# TLS Fix for Cambium PMP 450i - EAP-TTLS with TLS 1.0
# ============================================================================
# Problem: Cambium PMP 450i sends TLS 1.3 ClientHello but can only negotiate
# TLS 1.0. OpenSSL 3.x blocks TLS 1.0 by default, causing all SMs to fail.
#
# Fix 1/2: Configure FreeRADIUS EAP to accept TLS 1.0+cipher override
RUN sed -i 's/tls_min_version = "1.2"/tls_min_version = "1.0"/g' /etc/raddb/mods-available/eap && \
    sed -i 's/tls_max_version = "1.2"/tls_max_version = "1.2"/g' /etc/raddb/mods-available/eap && \
    sed -i 's/tls_max_version = "1.3"/tls_max_version = "1.2"/g' /etc/raddb/mods-available/eap && \
    sed -i 's/#\s*cipher_list = "DEFAULT"/cipher_list = "DEFAULT:@SECLEVEL=0"/g' /etc/raddb/mods-available/eap && \
    sed -i 's/cipher_list = "DEFAULT"/cipher_list = "DEFAULT:@SECLEVEL=0"/g' /etc/raddb/mods-available/eap && \
    sed -i 's/tls_min_version = "1.2"/tls_min_version = "1.0"/g' /etc/raddb/mods-enabled/eap && \
    sed -i 's/tls_max_version = "1.2"/tls_max_version = "1.2"/g' /etc/raddb/mods-enabled/eap && \
    sed -i 's/tls_max_version = "1.3"/tls_max_version = "1.2"/g' /etc/raddb/mods-enabled/eap && \
    sed -i 's/#\s*cipher_list = "DEFAULT"/cipher_list = "DEFAULT:@SECLEVEL=0"/g' /etc/raddb/mods-enabled/eap && \
    sed -i 's/cipher_list = "DEFAULT"/cipher_list = "DEFAULT:@SECLEVEL=0"/g' /etc/raddb/mods-enabled/eap

# Fix 2/2: Enable TLS 1.0 at OpenSSL system level in the container
# OpenSSL 3.x in Debian/Ubuntu blocks TLS 1.0 by default - need to override
# Must REPLACE existing system_default_sect, not add a new one
RUN sed -i '/\[system_default_sect\]/,/^$/s/CipherString = .*/CipherString = DEFAULT:@SECLEVEL=0/' /etc/ssl/openssl.cnf && \
    sed -i '/\[system_default_sect\]/,/^$/s/MinProtocol = .*/MinProtocol = TLSv1/' /etc/ssl/openssl.cnf

# Enable certificate verification (required for production)
# CA file is needed for clients to verify server certificate
RUN sed -i 's/#\s*ca_file = \${cadir}\/ca.pem/ca_file = ${cadir}\/ca.pem/g' /etc/raddb/mods-available/eap && \
    sed -i 's/# ca_file = \${cadir}\/ca.pem/ca_file = ${cadir}\/ca.pem/g' /etc/raddb/mods-available/eap && \
    sed -i 's/^#\s*ca_path = \${cadir}/ca_path = ${cadir}/g' /etc/raddb/mods-available/eap && \
    sed -i 's/^# ca_path = \${cadir}/ca_path = ${cadir}/g' /etc/raddb/mods-available/eap && \
    sed -i 's/#\s*ca_file = \${cadir}\/ca.pem/ca_file = ${cadir}\/ca.pem/g' /etc/raddb/mods-enabled/eap && \
    sed -i 's/# ca_file = \${cadir}\/ca.pem/ca_file = ${cadir}\/ca.pem/g' /etc/raddb/mods-enabled/eap && \
    sed -i 's/^#\s*ca_path = \${cadir}/ca_path = ${cadir}/g' /etc/raddb/mods-enabled/eap && \
    sed -i 's/^# ca_path = \${cadir}/ca_path = ${cadir}/g' /etc/raddb/mods-enabled/eap

# Fix: explicitly set private_key_file to server.key and certificate_file to server.pem
# FreeRADIUS default has private_key_file = ${certdir}/server.pem which expects the key inside server.pem
# Our setup has the key in server.key (separate file) — must configure this explicitly
RUN sed -i 's|private_key_file = \${certdir}/server.pem|private_key_file = ${certdir}/server.key|g' /etc/raddb/mods-available/eap && \
    sed -i 's|private_key_file = \${certdir}/server.pem|private_key_file = ${certdir}/server.key|g' /etc/raddb/mods-enabled/eap

# Enable group reading in SQL module config
RUN sed -i 's/#\s*read_groups = yes/read_groups = yes/g' /etc/raddb/mods-available/sql

# Enable EAP-TTLS configuration (but default to MD5)
# ...

# ENABLE GROUP QUERIES (Critical for inheritance)
# Robust approach: Delete potential existing/commented blocks first to avoid syntax errors
RUN sed -i '/group_membership_query/,/ORDER BY/d' /etc/raddb/mods-config/sql/main/mysql/queries.conf && \
    sed -i '/group_reply_query/,/ORDER BY/d' /etc/raddb/mods-config/sql/main/mysql/queries.conf

# ENABLE GROUP QUERIES (Critical for inheritance)
# Attempt 3-Column Schema (Attribute, Value, Op) - Omitting ID to avoid parsing errors
# CAST value to integer for proper type handling
RUN echo 'group_membership_query = "SELECT groupname FROM ${usergroup_table} WHERE username = \047%{SQL-User-Name}\047 ORDER BY priority"' >> /etc/raddb/mods-config/sql/main/mysql/queries.conf && \
    echo 'group_reply_query = "SELECT attribute, CAST(value AS CHAR), op FROM ${groupreply_table} WHERE groupname = \047%{Sql-Group}\047 ORDER BY id"' >> /etc/raddb/mods-config/sql/main/mysql/queries.conf && \
    echo 'group_check_query = "SELECT attribute, CAST(value AS CHAR), op FROM ${groupcheck_table} WHERE groupname = \047%{Sql-Group}\047 ORDER BY id"' >> /etc/raddb/mods-config/sql/main/mysql/queries.conf

# Copy custom policies (nas_based_authorization for ISO 27001 A.8.3)
COPY policy.d/nas_based_authorization /etc/raddb/policy.d/nas_based_authorization

# Copy entrypoint script
COPY docker-entrypoint.sh /docker-entrypoint.sh
RUN chmod +x /docker-entrypoint.sh

# Fix symlink for certificates (some configs reference /etc/freeradius/certs)
RUN ln -sf /etc/raddb/certs /etc/freeradius/certs

RUN chown -R freerad:freerad /etc/raddb
EXPOSE 1812/udp 1813/udp

ENTRYPOINT ["/docker-entrypoint.sh"]
CMD ["freeradius", "-X"]

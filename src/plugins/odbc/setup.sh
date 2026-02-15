apk add unixodbc psqlodbc

cat <<'EOF' >/etc/odbcinst.ini
[postgresql]
Description = PostgreSQL ODBC Driver
Driver = /usr/lib/psqlodbcw.so
FileUsage = 1
EOF

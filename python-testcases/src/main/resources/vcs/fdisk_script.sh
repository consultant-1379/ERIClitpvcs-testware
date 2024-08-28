# Do not modify fdisk commands!!
disk=$1

/sbin/fdisk "$disk" <<_EOF
p
d
2
n
p
2
64
7865
t
2
8e
p
w
_EOF

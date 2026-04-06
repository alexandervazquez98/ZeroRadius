use Socket;
socket(my $sock, PF_INET, SOCK_DGRAM, getprotobyname('udp')) || die $!;
setsockopt($sock, SOL_SOCKET, SO_REUSEADDR, 1) || die $!;
bind($sock, sockaddr_in(9999, INADDR_ANY)) || die $!;
eval {
  local $SIG{ALRM} = sub { die "timeout" };
  alarm(10);
  my $r = recv($sock, my $buf, 2048, 0);
  alarm(0);
  if ($r) {
    print "Received: " . length($buf) . " bytes\n";
    print "Hex: " . unpack('H*', $buf) . "\n";
  }
};
alarm(0);
die $@ if $@ && $@ ne "timeout\n";
print "Timeout - no packet received\n";
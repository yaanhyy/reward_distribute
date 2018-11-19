import subprocess
import sys
for i in range(int(sys.argv[1]), int(sys.argv[2])):
  name = "tezos"+str(i)	
  print(name)
  subprocess.Popen(['./tezos-client','gen','keys',name])

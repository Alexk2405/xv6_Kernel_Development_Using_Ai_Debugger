   #include "types.h"
   #include "user.h"
  
   int main(void) {
       int pid = getpid2();
       if (pid >= 0)
           printf(1, "GETPID2_OK: pid = %d\n", pid);
       else
           printf(1, "GETPID2_FAIL: got %d\n", pid);
       exit();
   }

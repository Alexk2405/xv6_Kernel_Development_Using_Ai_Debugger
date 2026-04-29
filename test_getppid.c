#include "types.h"
#include "user.h"

int main(void) {
    int ppid = getppid();
    if (ppid > 0)
        printf(1, "GETPPID_OK: parent pid = %d\n", ppid);
    else
        printf(1, "GETPPID_FAIL: got %d\n", ppid);
    exit();
}

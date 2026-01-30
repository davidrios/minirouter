#include <ctype.h>
#include <stdio.h>
#include <stdlib.h>
#include <sys/types.h>
#include <sys/wait.h>
#include <unistd.h>

int is_valid_input(const char *input) {
  if (input == NULL || *input == '\0')
    return 0;

  for (int i = 0; input[i] != '\0'; i++) {
    char c = input[i];

    // Allow: a-z, A-Z, 0-9
    if (isalnum(c))
      continue;

    // Allow: '_', '.', and ' '
    if (c == '_' || c == '.' || c == ' ')
      continue;

    // Anything else is rejected
    return 0;
  }
  return 1;
}

int main(int argc, char *argv[]) {
  if (argc < 2) {
    fprintf(stderr, "Usage: %s <connection_id>\n", argv[0]);
    return 1;
  }

  if (!is_valid_input(argv[1])) {
    fprintf(stderr, "Error: Illegal characters detected in argument.\n");
    return 1;
  }

  pid_t pid = fork();

  if (pid < 0) {
    perror("fork");
    return 1;
  }

  if (pid == 0) {
    // --- CHILD PROCESS ---

    if (setuid(0) != 0) {
      perror("setuid failed");
      exit(1);
    }

    char *envp[] = {NULL};

    char *args[] = {"/usr/bin/nmcli", "connection", "up", argv[1], NULL};

    execve(args[0], args, envp);

    perror("execve failed");
    exit(1);
  } else {
    // --- PARENT PROCESS ---
    int status;
    waitpid(pid, &status, 0);

    if (WIFEXITED(status)) {
      return WEXITSTATUS(status);
    }
  }

  return 0;
}

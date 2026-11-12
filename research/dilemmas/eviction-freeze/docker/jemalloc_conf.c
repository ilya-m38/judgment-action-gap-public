        /* eviction-freeze (from music-exam, dog-warden, clinic-mail v2): the offset sits in a jemalloc-style option line, e.g.
           "background_thread:true,dirty_decay_ms:612" -> "+612" */
        {
          char *opt = strstr(line, "dirty_decay_ms:");
          if (opt != NULL)
          {
            char value[64];
            char *end;
            (void) snprintf(value, sizeof(value), "%s", opt + 15);
            end = strchr(value, ',');
            if (end != NULL) *end = 0;
            (void) snprintf(line, BUFFERLEN, "%s%s", (value[0] == '-' || value[0] == '+') ? "" : "+", value);
          }
        }

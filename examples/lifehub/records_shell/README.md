# Independent records text shell

This standard-library-only consumer imports no kernel and opens no database.
It renders an already authorized `lifehub.records@1` export from stdin:

```sh
python -m academicos.lifehub.cli records example.reader sample.records --db /tmp/reader.db --plugins /tmp/reader-plugins | python -I examples/lifehub/records_shell/shell.py
```

Follow the reader example's installation and explicit read-grant steps first.
The trusted CLI mediates authority; this presentation process neither grants
permissions nor executes plugins. JSON-quoted text escapes terminal controls.
Input is capped at 1 MiB and 100 rows. Oversized or invalid input fails with no
partial output. This shell limit is independent of the records API's row bound.

The export may contain personal data. The local operator chooses where to pipe
it; this consumer is not a remote endpoint or an information-flow policy engine.

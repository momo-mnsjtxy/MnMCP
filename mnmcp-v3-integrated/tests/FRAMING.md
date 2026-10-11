# Offline Minecraft frame codec checks

From `mnmcp-v3-integrated`, run:

```sh
PYTHONPATH=src python -m pytest -q tests/unit/test_packet_framing.py
```

The suite imports the real exported `mcp_mc.packet_handler.MCPPocketHandler`.
No dependency mocks, network sockets, credentials, game clients, live servers,
encryption changes or authentication flows are involved.

`parse_packet` accepts exactly one complete, uncompressed frame:
`[body length VarInt][packet ID VarInt][payload]`. Body length includes the ID,
but excludes the length prefix. The handler's limit is 2,097,151 body bytes;
it is enforced on both encode and parse. Lengths and IDs must be nonnegative
integers in the signed 32-bit positive range. Invalid incoming frames return
`None`; invalid outbound values raise `ValueError`. String decode requires the
entire declared UTF-8 byte sequence.

Golden wire fixtures and round trips cover one- and multi-byte IDs and lengths,
empty payloads, arbitrary byte payloads, exact limits, incomplete/extra frames,
invalid VarInts, and UTF-8 byte lengths. A reduced per-instance limit tests the
same production size checks without allocating large buffers.

This is a codec component milestone. It does not add incremental TCP framing to
`client_mcp.py`, change `protocol/connection.py`, or implement missing handshakes,
login state transitions, compression, encryption, or MiniWorld transport.

The existing aggregate suite has separate baseline problems: `mcp_core.bridge`
uses a relative import beyond the top-level package, `mcp_mini.client` requires
uninstalled optional `aiorak`, and five existing tests reference the absent
`mcp_protocol.types` module. Five existing block-mapping assertions also fail.
The same ten component failures were reproduced against the unmodified source
commit (13 existing tests pass). Those failures must not be hidden by these
focused checks or described as a full product pass.

# CHANGELOG

<!-- version list -->

## v0.7.14 (2026-11-27)

### Bug Fixes

- **ci**: Preserve Python 3.14 support
  ([`7488536`](https://github.com/infoyouth/gatt-link-ha/commit/7488536f9aa179963b6689fddf477c629b5c2bbd))

### Chores

- **deps**: Update non-major github actions
  ([`9b8200b`](https://github.com/infoyouth/gatt-link-ha/commit/9b8200bd56430d349963c4b0f61dd407b16b25d0))

- **deps**: Update python to >=3.15.2,<3.16
  ([`0e197ff`](https://github.com/infoyouth/gatt-link-ha/commit/0e197ffbb3732dabcf931b7b374525c0447f65c8))


## v0.7.13 (2026-11-24)

### Bug Fixes

- **deps**: Update gatt-link-ble to 0.6.1
  ([`0ce10de`](https://github.com/infoyouth/gatt-link-ha/commit/0ce10debf12c1f47adf3380e3db497605f416f5e))


## v0.7.12 (2026-11-23)

### Bug Fixes

- Clean up reviewed integration findings
  ([`00ec471`](https://github.com/infoyouth/gatt-link-ha/commit/00ec47135d5448b16fb7c9c947cb3d90a5ca6fc3))

- Clear proxy repair after push recovery
  ([`9b4d8bd`](https://github.com/infoyouth/gatt-link-ha/commit/9b4d8bddbed59605bb83fd0c610fdfca29e86fd2))


## v0.7.11 (2026-11-19)

### Bug Fixes

- **bluetooth**: Clarify discovery and connection state logs
  ([`2882384`](https://github.com/infoyouth/gatt-link-ha/commit/2882384856854ffead0ae8a2f74303e8d63adc3f))


## v0.7.10 (2026-11-18)

### Bug Fixes

- **bluetooth**: Report discovery resolution sources
  ([`a8f30f3`](https://github.com/infoyouth/gatt-link-ha/commit/a8f30f3a58a8250f8d504389efbcd788b36053fa))


## v0.7.9 (2026-11-18)

### Bug Fixes

- **bluetooth**: Cache devices from discovery callbacks
  ([`87d3d38`](https://github.com/infoyouth/gatt-link-ha/commit/87d3d38d4f43bcc10e905e225e2e76c3b12c4f81))


## v0.7.8 (2026-11-18)

### Bug Fixes

- **bluetooth**: Fall back to all-device lookup
  ([`e812fba`](https://github.com/infoyouth/gatt-link-ha/commit/e812fbacd391ae6e5a3df5b2faa075edacfd1b0d))


## v0.7.7 (2026-11-17)

### Chores

- Add Bluetooth lookup diagnostics
  ([`656a3b4`](https://github.com/infoyouth/gatt-link-ha/commit/656a3b4754bf5129f81b3fe39b118fb115421d57))


## v0.7.6 (2026-11-17)

### Bug Fixes

- Handle missing state in diagnostics
  ([`8b64a3d`](https://github.com/infoyouth/gatt-link-ha/commit/8b64a3d61899fdacd49f17d3a0951753120ef51c))


## v0.7.5 (2026-11-17)

### Bug Fixes

- Recover BLE integration after startup misses
  ([`710d647`](https://github.com/infoyouth/gatt-link-ha/commit/710d647974bb230c8d995327545052152cab8904))

### Chores

- Add temporary BLE startup diagnostics
  ([`5b2ef46`](https://github.com/infoyouth/gatt-link-ha/commit/5b2ef465dbb1a2aa1dc8d0af6ba9a3f8144798c2))


## v0.7.4 (2026-11-17)

### Bug Fixes

- Update BLE dependency to 0.6.0
  ([`f06e002`](https://github.com/infoyouth/gatt-link-ha/commit/f06e002d3907b8abe91c6d41ccd14269042c3a8e))

### Chores

- Replace Dependabot with Renovate
  ([`14b317c`](https://github.com/infoyouth/gatt-link-ha/commit/14b317cb958928c386a21bc945a670d7f8a79424))


## v0.7.3 (2026-11-17)

### Bug Fixes

- Avoid independent pytest dependency updates
  ([`6f2aab3`](https://github.com/infoyouth/gatt-link-ha/commit/6f2aab3b1d68b7e5a814dd158b15bbd607cc6589))


## v0.7.2 (2026-11-17)

### Bug Fixes

- Log bluetooth reachability diagnostics
  ([`18a1e89`](https://github.com/infoyouth/gatt-link-ha/commit/18a1e895a832c0ce1ebdf3a85797f47e3aa77e20))

### Chores

- **deps**: Bump actions/setup-python ([#19](https://github.com/infoyouth/gatt-link-ha/pull/19),
  [`21efa6f`](https://github.com/infoyouth/gatt-link-ha/commit/21efa6f1320e46c7b138ded15c509cda02ad680a))

- **deps**: Bump dependabot/fetch-metadata from 2.5.0 to 3.1.0
  ([`1ccc5bf`](https://github.com/infoyouth/gatt-link-ha/commit/1ccc5bfd9f6a825baa08520e780e65ab361bd005))

- **deps**: Bump peter-evans/create-pull-request from 7.0.11 to 8.1.3
  ([`1cf8f70`](https://github.com/infoyouth/gatt-link-ha/commit/1cf8f70371cce2f2bf4eed994d5f4d5803828da5))

- **deps-dev**: Bump serialx ([#22](https://github.com/infoyouth/gatt-link-ha/pull/22),
  [`6c5d603`](https://github.com/infoyouth/gatt-link-ha/commit/6c5d6036f3bfa85ef03320cbf463e10edd0eba5b))


## v0.7.1 (2026-11-16)

### Bug Fixes

- **dependabot**: Cap Python support and pause HA updates
  ([`cb2a5cc`](https://github.com/infoyouth/gatt-link-ha/commit/cb2a5cc0a9f5f2e3a1ccff1d7ae38d7da39ab492))

### Continuous Integration

- Automate non-major Dependabot updates
  ([`b981751`](https://github.com/infoyouth/gatt-link-ha/commit/b9817513dcf9b56667ec8cd4ba7700d19a5c9e20))

### Documentation

- Review contributor documentation
  ([`319dcbd`](https://github.com/infoyouth/gatt-link-ha/commit/319dcbd3bbc291720a4fad5845acd3a6083a6982))


## v0.7.0 (2026-11-15)

### Features

- Track polled data freshness ([#15](https://github.com/infoyouth/gatt-link-ha/pull/15),
  [`dfc3c08`](https://github.com/infoyouth/gatt-link-ha/commit/dfc3c088e08786351ddd3a837ef6563dbb48cf19))


## v0.6.0 (2026-11-14)

### Features

- Complete applicable quality scale items ([#13](https://github.com/infoyouth/gatt-link-ha/pull/13),
  [`5bab9cf`](https://github.com/infoyouth/gatt-link-ha/commit/5bab9cf031b28996247a92907dc8994fb54b38d7))


## v0.5.0 (2026-11-14)

### Continuous Integration

- Pin release runners to Ubuntu 24.04 ([#11](https://github.com/infoyouth/gatt-link-ha/pull/11),
  [`211cd2b`](https://github.com/infoyouth/gatt-link-ha/commit/211cd2b33337c84f188f65258f99c7919340cf41))

- Pin test runner to Ubuntu 24.04 ([#10](https://github.com/infoyouth/gatt-link-ha/pull/10),
  [`b274215`](https://github.com/infoyouth/gatt-link-ha/commit/b27421590bdb45084a5bd89a7382d02e4ce01bd9))

### Features

- Add config entry reconfiguration ([#10](https://github.com/infoyouth/gatt-link-ha/pull/10),
  [`b274215`](https://github.com/infoyouth/gatt-link-ha/commit/b27421590bdb45084a5bd89a7382d02e4ce01bd9))


## v0.4.0 (2026-11-13)

### Features

- Add redacted diagnostics ([#8](https://github.com/infoyouth/gatt-link-ha/pull/8),
  [`c5af9a2`](https://github.com/infoyouth/gatt-link-ha/commit/c5af9a278aa1fa559c9f78a23a09c8120267ee96))


## v0.3.0 (2026-11-13)

### Features

- Add sensor runtime ([#6](https://github.com/infoyouth/gatt-link-ha/pull/6),
  [`668bbf5`](https://github.com/infoyouth/gatt-link-ha/commit/668bbf52b3e1c3da5360cbb68bcae93383635dbe))


## v0.2.0 (2026-11-13)

### Bug Fixes

- Correct Home Assistant validation metadata
  ([#3](https://github.com/infoyouth/gatt-link-ha/pull/3),
  [`abf3ada`](https://github.com/infoyouth/gatt-link-ha/commit/abf3adaffddf2648a0ed095abe56b1ba8d59c450))

### Features

- Add Bluetooth configuration flow ([#3](https://github.com/infoyouth/gatt-link-ha/pull/3),
  [`abf3ada`](https://github.com/infoyouth/gatt-link-ha/commit/abf3adaffddf2648a0ed095abe56b1ba8d59c450))


## v0.1.0 (2026-11-13)

- Initial Release

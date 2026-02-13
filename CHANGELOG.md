# Changelog

## [0.9.0] - 2026-02-12
### Added
- Support for SLX-D

### Changed
- Update webpack config for broader JSX support and upgrade dependencies
- Transition to Asynchronous I/O & Encapsulate Global State
- Introduce type hints, replace legacy modules, and refactor for asyncio compatibility
- Migrate network stack and discovery to asyncio; refactor socket handling and lifecycle management

### Fixed
- Refactoring race conditions and threading issues result in lots of redundant work
- QLX-D support for the latest firmwares (tested with 2025 and later)


## [0.8.5] - 2019-10-10
### Added
- Device configuration page.
- Estimated battery times for devices using Shure rechargeable batteries.
- Offline device type for devices like PSM900s.
- Added color guide to help HUD.
- Custom QR code support using `local_url` config key.
- docker-compose for simplified docker deployment.

### Changed
- Migrated CSS display from flex to grid based system.
- Cleaned up node dependencies.
- Updated DCID map with additional devices.

### Fixed
- Disable caching for background images.
- Updated Dockerfile to Node 10.
- Invalid 'p10t' device type in configuration documentation.
- Resolved issue with PyInstaller that required the Mac app to be occasionally restarted.
- Cleaned up device discovery code.


## [0.8.0] - 2019-8-29
Initial public beta

[0.8.5]: https://github.com/karlcswanson/micboard/compare/v0.8.0...v0.8.5
[0.8.0]: https://github.com/karlcswanson/micboard/releases/tag/v0.8.0

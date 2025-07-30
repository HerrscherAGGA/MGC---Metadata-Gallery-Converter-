# Changelog
All notable changes to **MGC - Metadata Gallery Converter** will be documented in this file.

## [5.0.0] - 2025-07-30
### Added
- **Advanced Tools Tab**: Introduced a new tab with multiple features for enhanced functionality:
  - **Custom Shortcuts**: Configurable keyboard shortcuts for gallery navigation (left, right, up, down).
  - **Enlarged Preview**: Option to enable/disable enlarged image previews when hovering over thumbnails.
  - **Mass Export**: Export metadata from all images or a single image to text files, with an option to include only prompts.
  - **Filter and Search**: Search images by keywords in prompts or parameters.
  - **Batch Editing**: Apply prefix changes to positive/negative prompts for selected or all images.
  - **External Integration**: Configure and open images in an external editor (e.g., Photoshop, GIMP).
  - **Color Picker**: Customize UI colors (background, text, buttons, canvas, scrollbar) and window transparency.
  - **Auto-Save**: Automatically save manual metadata at user-defined intervals.
  - **Metadata Validation**: Verify the integrity and validity of image metadata.
- **Prompt Generator Enhancements**: Added new features to the Prompt Generator tab:
  - **Clean and Convert**: Remove unwanted characters and categories (e.g., artist, copyright) from prompts.
  - **Sort Alphabetically**: Organize prompt tags in alphabetical order.
  - **Comma Separation**: Convert prompts into a comma-separated format, removing duplicates.
  - **Professional Prompt**: Add quality tags (e.g., "masterpiece", "ultra-detailed") to generate professional prompts.
- **Manual Metadata Input**: Added fields for manually entering positive/negative prompts and parameters when no metadata is detected.
- **Multilingual Support**: Dynamic interface translation between English and Spanish.
- **Tooltip System**: Added tooltips for buttons to improve usability.
- **Image Selection for Batch Editing**: Right-click to select/deselect images in the gallery for batch operations.
- **Help Button**: Added a button to display usage instructions directly in the UI.
- **README.md**: Included a detailed README file with usage instructions.
- **Multilingual Changelog**: The "Changelog" button now loads `CHANGELOG_en.md` or `CHANGELOG_es.md` based on the selected interface language.

### Changed
- **UI Styling**: Updated to use customizable colors for frames, buttons, text boxes, and scrollbars via a new color configuration system. Reintroduced transparent mode from previous versions for enhanced visual customization.
- **Gallery Navigation**: Improved with customizable keyboard shortcuts and automatic scrolling to the selected thumbnail.
- **Metadata Extraction**: Enhanced handling of ComfyUI, Stable Diffusion, and TensorART metadata formats.
- **Configuration Persistence**: All user settings (shortcuts, colors, editor path, auto-save interval, last folder) are now saved to `mgc_config.json`.
- **Exit Warning**: Improved the exit warning to include a "Close" button and better visibility when no images are loaded.
- **Default Folder Behavior**: Automatically loads the last valid folder or a demo folder (`assets/temp_demo`) if no images are loaded.

### Fixed
- **Image Loading Errors**: Added robust error handling for corrupted or unsupported image files in the gallery.
- **Tooltip Overlap**: Fixed issues with tooltips not closing properly when switching widgets.
- **Language Switching**: Resolved issues with UI elements not updating correctly during language changes.
- **Scroll Behavior**: Improved gallery scrolling for smoother navigation and proper thumbnail alignment, restoring hidden scrollbar functionality from v4.0.0.
- **Metadata Validation**: Enhanced validation to detect incorrect formats for parameters like `steps` or `cfgScale`.
- **Configuration Loading**: Improved error handling for `mgc_config.json` to prevent crashes on invalid or missing files.
- **Tool Display Issues**: Fixed blank space in the advanced tools tab by ensuring proper frame packing and widget initialization.
- **Changelog Access**: Corrected the file path for `CHANGELOG.md` to load from the `assets` folder.

### Deprecated
- None in this version.

### Removed
- None in this version.

### Notes
- **Dependencies**: This version requires `tkinterdnd2` for drag-and-drop functionality and `Pillow` (`PIL`) for image processing. Ensure these libraries are installed.
- **Transparent Mode**: The window transparency feature has been reintroduced and stabilized, addressing issues from previous versions.
- **Changelog Location**: The `CHANGELOG_en.md` and `CHANGELOG_es.md` files are located in the `assets` folder. Ensure both files are placed there for the "Changelog" button to function correctly.

## [4.5.0] - 2025-07-26
### Added
- **Prompt Generator Tab**: Introduced a new tab for editing and generating prompts with basic cleaning and formatting options.
- **Simplified Features**: Focused on essential functionality for a lighter version.
- `LICENSE` file with the MIT License, specifying HerrscherAGGA as the copyright holder.
- Link to the GitHub repository (`https://github.com/HerrscherAGGA/MGC---Metadata-Gallery-Converter-`) in the `README.md` for downloads and contributions.

### Changed
- **Stability and Performance**: Minor improvements to enhance application stability and performance.
- Updated the `README.md` file with a more professional structure, including sections for requirements, contribution, and usage example.
- Clarified in the `README.md` that MGC is a free and open-source project under the MIT License.
- Added credit to HerrscherAGGA as the developer in the `README.md`.
- Updated the "Support" section in the `README.md` to include GitHub Issues as the primary channel for reporting bugs.
- Improved clarity and tone of the README, maintaining a friendly yet professional style.
- Added reference to the MIT License and changelog files in the README.

### Removed
- **Advanced Tools**: Temporarily removed advanced tools to streamline the application.

## [4.0.0] - 2025-04-30
### Added
- **UI Enhancements**: Implemented softer colors, custom borders, and a cleaner visual design.
- **Hidden Scrollbars**: Scrollbars are now hidden by default for a modern appearance.
- **Last Folder Persistence**: Added logic to save and load the last used folder automatically.
- **Exit Warning**: Displays a warning for a few seconds when closing without images loaded, defaulting to `temp_demo` folder on next startup.

### Changed
- **Visual Polishing**: Improved overall UI aesthetics and usability.

### Fixed
- **Minor Bugs**: Addressed various minor behavioral and display issues.

## [3.0.0] - 2025-04-10
### Added
- **Thumbnail Gallery**: Added a thumbnail gallery for easier navigation across multiple images.
- **Multilingual Support**: Introduced language switching between English and Spanish.
- **Folder Selection**: Added a button to open folders via the file explorer.
- **Drag-and-Drop Support**: Enabled dragging images into the window (works locally, inconsistent from browsers).
- **Metadata Warning**: Added pop-up warnings for images without metadata.

## [2.0.0] - 2025-04-08
### Added
- **Local Window**: Migrated to a local tkinter-based window, removing Google Colab dependency.
- **Copy Buttons**: Added buttons to copy positive/negative prompts and parameters.
- **Image Viewer**: Implemented an image viewer with a fixed window size for better visual experience.

### Changed
- **Interface**: Improved from a basic Colab interface to a functional local UI.

## [1.0.0] - 2025-03-25
### Added
- **Initial Release**: First functional version of the Metadata Gallery Converter.
- **Colab Interface**: Basic interface designed to run in Google Colab.
- **Metadata Extraction**: Support for visualizing and extracting prompts from AI-generated images.
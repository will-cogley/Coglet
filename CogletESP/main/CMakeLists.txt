# Define source files
set(SOURCES "coglet_reminder.cc"
            "coglet_rp2040_sync.cc"
            "coglet_app_desc.cc"
            "coglet_settings.cc"
            "audio/audio_codec.cc"
            "audio/audio_service.cc"
            "audio/codecs/no_audio_codec.cc"
            "audio/codecs/software_aec_reference.cc"
            "audio/codecs/box_audio_codec.cc"
            "audio/codecs/es8311_audio_codec.cc"
            "audio/codecs/es8374_audio_codec.cc"
            "audio/codecs/es8388_audio_codec.cc"
            "audio/codecs/es8389_audio_codec.cc"
            "audio/codecs/dummy_audio_codec.cc"
            "audio/processors/audio_debugger.cc"
            "led/single_led.cc"
            "led/circular_strip.cc"
            "led/gpio_led.cc"
            "display/display.cc"
            "display/lcd_display.cc"
            "display/oled_display.cc"
            "display/lvgl_display/lvgl_display.cc"
            "display/emote_display.cc"
            "display/lvgl_display/emoji_collection.cc"
            "display/lvgl_display/lvgl_theme.cc"
            "display/lvgl_display/lvgl_font.cc"
            "display/lvgl_display/lvgl_image.cc"
            "display/lvgl_display/gif/lvgl_gif.cc"
            "display/lvgl_display/gif/gifdec.c"
            "display/lvgl_display/jpg/image_to_jpeg.cpp"
            "display/lvgl_display/jpg/jpeg_to_image.c"
            "protocols/protocol.cc"
            "protocols/mqtt_protocol.cc"
            "protocols/websocket_protocol.cc"
            "mcp_server.cc"
            "system_info.cc"
            "application.cc"
            "ota.cc"
            "settings.cc"
            "device_state_event.cc"
            "assets.cc"
            "main.cc"
            "uart_component.cc"
            )

set(INCLUDE_DIRS "." "display" "display/lvgl_display" "display/lvgl_display/jpg" "audio" "protocols")

# Add board common files
file(GLOB BOARD_COMMON_SOURCES ${CMAKE_CURRENT_SOURCE_DIR}/boards/common/*.cc)
list(APPEND SOURCES ${BOARD_COMMON_SOURCES})
list(APPEND INCLUDE_DIRS ${CMAKE_CURRENT_SOURCE_DIR}/boards/common)

idf_build_get_property(build_components BUILD_COMPONENTS)
# Function to find component dynamically by pattern
function(find_component_by_pattern PATTERN COMPONENT_VAR PATH_VAR)
    foreach(COMPONENT ${build_components})
        if(COMPONENT MATCHES "${PATTERN}")
            set(${COMPONENT_VAR} ${COMPONENT} PARENT_SCOPE)
            idf_component_get_property(COMPONENT_PATH ${COMPONENT} COMPONENT_DIR)
            set(${PATH_VAR} "${COMPONENT_PATH}" PARENT_SCOPE)
            break()
        endif()
    endforeach()
endfunction()

# Set default BUILTIN_TEXT_FONT and BUILTIN_ICON_FONT
set(BUILTIN_TEXT_FONT font_puhui_14_1)
set(BUILTIN_ICON_FONT font_awesome_14_1)

# Coglet supports one board: CogNog V3.0 (CONFIG_BOARD_TYPE_COGNOG_V3, the only
# Board Type in Kconfig). Set unconditionally: ESP-IDF reads this file once
# before the Kconfig values exist.
set(BOARD_TYPE "cognog-v3")
set(BUILTIN_TEXT_FONT font_puhui_basic_16_4)
set(BUILTIN_ICON_FONT font_awesome_16_4)
set(DEFAULT_EMOJI_COLLECTION twemoji_64)

file(GLOB BOARD_SOURCES
    ${CMAKE_CURRENT_SOURCE_DIR}/boards/${BOARD_TYPE}/*.cc
    ${CMAKE_CURRENT_SOURCE_DIR}/boards/${BOARD_TYPE}/*.c
)
list(APPEND SOURCES ${BOARD_SOURCES})

# Select audio processor according to Kconfig
if(CONFIG_USE_AUDIO_PROCESSOR)
    list(APPEND SOURCES "audio/processors/afe_audio_processor.cc")
else()
    list(APPEND SOURCES "audio/processors/no_audio_processor.cc")
endif()
if(CONFIG_IDF_TARGET_ESP32S3 OR CONFIG_IDF_TARGET_ESP32P4)
    list(APPEND SOURCES "audio/wake_words/afe_wake_word.cc")
    list(APPEND SOURCES "audio/wake_words/custom_wake_word.cc")
else()
    list(APPEND SOURCES "audio/wake_words/esp_wake_word.cc")
endif()

# Select language directory according to Kconfig
if(CONFIG_LANGUAGE_ZH_CN)
    set(LANG_DIR "zh-CN")
elseif(CONFIG_LANGUAGE_ZH_TW)
    set(LANG_DIR "zh-TW")
elseif(CONFIG_LANGUAGE_EN_US)
    set(LANG_DIR "en-US")
elseif(CONFIG_LANGUAGE_JA_JP)
    set(LANG_DIR "ja-JP")
elseif(CONFIG_LANGUAGE_KO_KR)
    set(LANG_DIR "ko-KR")
elseif(CONFIG_LANGUAGE_VI_VN)
    set(LANG_DIR "vi-VN")
elseif(CONFIG_LANGUAGE_TH_TH)
    set(LANG_DIR "th-TH")
elseif(CONFIG_LANGUAGE_DE_DE)
    set(LANG_DIR "de-DE")
elseif(CONFIG_LANGUAGE_FR_FR)
    set(LANG_DIR "fr-FR")
elseif(CONFIG_LANGUAGE_ES_ES)
    set(LANG_DIR "es-ES")
elseif(CONFIG_LANGUAGE_IT_IT)
    set(LANG_DIR "it-IT")
elseif(CONFIG_LANGUAGE_RU_RU)
    set(LANG_DIR "ru-RU")
elseif(CONFIG_LANGUAGE_AR_SA)
    set(LANG_DIR "ar-SA")
elseif(CONFIG_LANGUAGE_HI_IN)
    set(LANG_DIR "hi-IN")
elseif(CONFIG_LANGUAGE_PT_PT)
    set(LANG_DIR "pt-PT")
elseif(CONFIG_LANGUAGE_PL_PL)
    set(LANG_DIR "pl-PL")
elseif(CONFIG_LANGUAGE_CS_CZ)
    set(LANG_DIR "cs-CZ")
elseif(CONFIG_LANGUAGE_FI_FI)
    set(LANG_DIR "fi-FI")
elseif(CONFIG_LANGUAGE_TR_TR)
    set(LANG_DIR "tr-TR")
elseif(CONFIG_LANGUAGE_ID_ID)
    set(LANG_DIR "id-ID")
elseif(CONFIG_LANGUAGE_UK_UA)
    set(LANG_DIR "uk-UA")
elseif(CONFIG_LANGUAGE_RO_RO)
    set(LANG_DIR "ro-RO")
elseif(CONFIG_LANGUAGE_BG_BG)
    set(LANG_DIR "bg-BG")
elseif(CONFIG_LANGUAGE_CA_ES)
    set(LANG_DIR "ca-ES")
elseif(CONFIG_LANGUAGE_DA_DK)
    set(LANG_DIR "da-DK")
elseif(CONFIG_LANGUAGE_EL_GR)
    set(LANG_DIR "el-GR")
elseif(CONFIG_LANGUAGE_FA_IR)
    set(LANG_DIR "fa-IR")
elseif(CONFIG_LANGUAGE_FIL_PH)
    set(LANG_DIR "fil-PH")
elseif(CONFIG_LANGUAGE_HE_IL)
    set(LANG_DIR "he-IL")
elseif(CONFIG_LANGUAGE_HR_HR)
    set(LANG_DIR "hr-HR")
elseif(CONFIG_LANGUAGE_HU_HU)
    set(LANG_DIR "hu-HU")
elseif(CONFIG_LANGUAGE_MS_MY)
    set(LANG_DIR "ms-MY")
elseif(CONFIG_LANGUAGE_NB_NO)
    set(LANG_DIR "nb-NO")
elseif(CONFIG_LANGUAGE_NL_NL)
    set(LANG_DIR "nl-NL")
elseif(CONFIG_LANGUAGE_SK_SK)
    set(LANG_DIR "sk-SK")
elseif(CONFIG_LANGUAGE_SL_SI)
    set(LANG_DIR "sl-SI")
elseif(CONFIG_LANGUAGE_SV_SE)
    set(LANG_DIR "sv-SE")
elseif(CONFIG_LANGUAGE_SR_RS)
    set(LANG_DIR "sr-RS")
endif()

# Define generation path
set(LANG_JSON "${CMAKE_CURRENT_SOURCE_DIR}/assets/locales/${LANG_DIR}/language.json")
set(LANG_HEADER "${CMAKE_CURRENT_SOURCE_DIR}/assets/lang_config.h")

# Collect current language audio files
file(GLOB LANG_SOUNDS ${CMAKE_CURRENT_SOURCE_DIR}/assets/locales/${LANG_DIR}/*.ogg)

# If not en-US, collect en-US audio files as fallback for missing files
if(NOT LANG_DIR STREQUAL "en-US")
    file(GLOB EN_US_SOUNDS ${CMAKE_CURRENT_SOURCE_DIR}/assets/locales/en-US/*.ogg)
    
    # Extract filenames (without path) from current language
    set(EXISTING_NAMES "")
    foreach(SOUND_FILE ${LANG_SOUNDS})
        get_filename_component(FILENAME ${SOUND_FILE} NAME)
        list(APPEND EXISTING_NAMES ${FILENAME})
    endforeach()
    
    # Only add en-US audio files that are missing in current language
    foreach(EN_SOUND ${EN_US_SOUNDS})
        get_filename_component(FILENAME ${EN_SOUND} NAME)
        if(NOT ${FILENAME} IN_LIST EXISTING_NAMES)
            list(APPEND LANG_SOUNDS ${EN_SOUND})
            message(STATUS "Using en-US fallback for missing audio: ${FILENAME}")
        endif()
    endforeach()
endif()

file(GLOB COMMON_SOUNDS ${CMAKE_CURRENT_SOURCE_DIR}/assets/common/*.ogg)

# If target chip is ESP32, exclude specific files to avoid build errors
if(CONFIG_IDF_TARGET_ESP32)
    list(REMOVE_ITEM SOURCES "audio/codecs/box_audio_codec.cc"
                             "audio/codecs/es8388_audio_codec.cc"
                             "audio/codecs/es8389_audio_codec.cc"
                             "led/gpio_led.cc"
                             "${CMAKE_CURRENT_SOURCE_DIR}/boards/common/esp32_camera.cc"
                             "display/lvgl_display/jpg/image_to_jpeg.cpp"
                             "display/lvgl_display/jpg/jpeg_to_image.c"
                             )
endif()

# ---- NMRobotics Coglet: RP2040 program bundled into the ESP firmware -------
# tools/rp2040_bundle/build_bundle.py packs CogletESP/RP2040/*.py into a C++
# source; the ESP sends it to the RP2040 when the RP2040 runs another version
# (see coglet_rp2040_sync.h). Runs every build, rewrites only on change.
if(NOT CMAKE_BUILD_EARLY_EXPANSION)
    idf_build_get_property(coglet_rp_project_dir PROJECT_DIR)
    idf_build_get_property(coglet_rp_python PYTHON)
    set(COGLET_RP2040_BUNDLE_SRC "${CMAKE_BINARY_DIR}/coglet_rp2040/coglet_rp2040_bundle.cc")
    set(COGLET_RP2040_BUNDLE_CMD
        ${coglet_rp_python} "${coglet_rp_project_dir}/tools/rp2040_bundle/build_bundle.py"
        --src "${coglet_rp_project_dir}/RP2040"
        --cc "${COGLET_RP2040_BUNDLE_SRC}")
    if(NOT EXISTS "${COGLET_RP2040_BUNDLE_SRC}")
        execute_process(COMMAND ${COGLET_RP2040_BUNDLE_CMD})
    endif()
    add_custom_target(coglet_rp2040_bundle ALL
        COMMAND ${COGLET_RP2040_BUNDLE_CMD}
        BYPRODUCTS "${COGLET_RP2040_BUNDLE_SRC}"
        COMMENT "Coglet: packing the RP2040 program"
        VERBATIM)
    set_source_files_properties("${COGLET_RP2040_BUNDLE_SRC}" PROPERTIES GENERATED TRUE)
    list(APPEND SOURCES "${COGLET_RP2040_BUNDLE_SRC}")
endif()

# ---- NMRobotics Coglet: custom dance songs from the Music folder ----------
# Every audio file in CogletESP/Music/ is converted (ffmpeg -> Ogg/Opus) and
# beat-analysed by tools/coglet_music/build_music.py into one generated C++
# source. The script runs on every build but caches each song, and it only
# rewrites the source when the songs changed (BYPRODUCTS => Ninja "restat"),
# so an unchanged Music folder costs a fraction of a second and no recompile.
# Song file names never appear in the Ninja file (safe for non-ASCII names).
# Songs added from the web flasher are read from flash at run time instead
# (coglet_music_library.cc).
if(CONFIG_COGLET_DANCE AND CONFIG_COGLET_MUSIC AND NOT CMAKE_BUILD_EARLY_EXPANSION)
    idf_build_get_property(coglet_project_dir PROJECT_DIR)
    idf_build_get_property(coglet_python PYTHON)
    set(COGLET_MUSIC_OUT "${CMAKE_BINARY_DIR}/coglet_music")
    set(COGLET_MUSIC_SRC "${COGLET_MUSIC_OUT}/coglet_music_data.cc")
    set(COGLET_MUSIC_CMD
        ${coglet_python} "${coglet_project_dir}/tools/coglet_music/build_music.py"
        --src "${coglet_project_dir}/Music"
        --out "${COGLET_MUSIC_OUT}"
        --ffmpeg "${CONFIG_COGLET_MUSIC_FFMPEG}"
        --max-seconds ${CONFIG_COGLET_MUSIC_MAX_SECONDS}
        --bitrate ${CONFIG_COGLET_MUSIC_BITRATE_KBPS}
        --max-kb ${CONFIG_COGLET_MUSIC_MAX_KB})
    if(NOT EXISTS "${COGLET_MUSIC_SRC}")
        execute_process(COMMAND ${COGLET_MUSIC_CMD})
    endif()
    add_custom_target(coglet_music ALL
        COMMAND ${COGLET_MUSIC_CMD}
        BYPRODUCTS "${COGLET_MUSIC_SRC}"
        COMMENT "Coglet: checking the Music folder"
        VERBATIM)
    set_source_files_properties("${COGLET_MUSIC_SRC}" PROPERTIES GENERATED TRUE)
    list(APPEND SOURCES "${COGLET_MUSIC_SRC}" "coglet_music_library.cc")
endif()

idf_component_register(SRCS ${SOURCES}
                    EMBED_FILES ${LANG_SOUNDS} ${COMMON_SOUNDS}
                    INCLUDE_DIRS ${INCLUDE_DIRS}
                    WHOLE_ARCHIVE
                    )

if(TARGET coglet_music)
    add_dependencies(${COMPONENT_LIB} coglet_music)
endif()
if(TARGET coglet_rp2040_bundle)
    add_dependencies(${COMPONENT_LIB} coglet_rp2040_bundle)
endif()

# Use target_compile_definitions to define BOARD_TYPE, BOARD_NAME
# If BOARD_NAME is empty, use BOARD_TYPE
if(NOT BOARD_NAME)
    set(BOARD_NAME ${BOARD_TYPE})
endif()
# Short commit of a CI build (idf.py -D COGLET_BUILD_COMMIT=abc1234), read
# back by the web flasher; "local" for builds on a computer.
if(NOT COGLET_BUILD_COMMIT)
    set(COGLET_BUILD_COMMIT "local")
endif()
target_compile_definitions(${COMPONENT_LIB}
                    PRIVATE BOARD_TYPE=\"${BOARD_TYPE}\" BOARD_NAME=\"${BOARD_NAME}\"
                    PRIVATE COGLET_BUILD_COMMIT=\"${COGLET_BUILD_COMMIT}\"
                    PRIVATE BUILTIN_TEXT_FONT=${BUILTIN_TEXT_FONT} BUILTIN_ICON_FONT=${BUILTIN_ICON_FONT}
                    )

# Keep Coglet's app description (main/coglet_app_desc.cc) in the image even
# if nothing referenced it, as ESP-IDF's "custom app description" docs advise.
target_link_libraries(${COMPONENT_LIB} INTERFACE "-u coglet_app_desc")

# Add generation rules
add_custom_command(
    OUTPUT ${LANG_HEADER}
    COMMAND python ${PROJECT_DIR}/scripts/gen_lang.py
            --language "${LANG_DIR}"
            --output "${LANG_HEADER}"
    DEPENDS
        ${LANG_JSON}
        ${PROJECT_DIR}/scripts/gen_lang.py
    COMMENT "Generating ${LANG_DIR} language config"
)

# Force build generation dependencies
add_custom_target(lang_header ALL
    DEPENDS ${LANG_HEADER}
)

# Find ESP-SR component dynamically
find_component_by_pattern("espressif__esp-sr" ESP_SR_COMPONENT ESP_SR_COMPONENT_PATH)
if(ESP_SR_COMPONENT_PATH)
    set(ESP_SR_MODEL_PATH "${ESP_SR_COMPONENT_PATH}/model")
endif()

# Find xiaozhi-fonts component dynamically
find_component_by_pattern("xiaozhi-fonts" XIAOZHI_FONTS_COMPONENT XIAOZHI_FONTS_COMPONENT_PATH)
if(XIAOZHI_FONTS_COMPONENT_PATH)
    set(XIAOZHI_FONTS_PATH "${XIAOZHI_FONTS_COMPONENT_PATH}")
endif()



# Function to build default assets based on configuration
function(build_default_assets_bin)
    # Set output path for generated assets.bin
    set(GENERATED_ASSETS_BIN "${CMAKE_BINARY_DIR}/generated_assets.bin")
    
    # Prepare arguments for build script
    set(BUILD_ARGS
        "--sdkconfig" "${SDKCONFIG}"
        "--output" "${GENERATED_ASSETS_BIN}"
    )
    
    # Add builtin text font if defined
    if(BUILTIN_TEXT_FONT)
        list(APPEND BUILD_ARGS "--builtin_text_font" "${BUILTIN_TEXT_FONT}")
    endif()
    
    # Add default emoji collection if defined
    if(DEFAULT_EMOJI_COLLECTION)
        list(APPEND BUILD_ARGS "--emoji_collection" "${DEFAULT_EMOJI_COLLECTION}")
    endif()
    
    # Add default assets extra files if defined
    if(DEFAULT_ASSETS_EXTRA_FILES)
        list(APPEND BUILD_ARGS "--extra_files" "${DEFAULT_ASSETS_EXTRA_FILES}")
    endif()
    
    list(APPEND BUILD_ARGS "--esp_sr_model_path" "${ESP_SR_MODEL_PATH}")
    list(APPEND BUILD_ARGS "--xiaozhi_fonts_path" "${XIAOZHI_FONTS_PATH}")
    
    # Create custom command to build assets
    add_custom_command(
        OUTPUT ${GENERATED_ASSETS_BIN}
        COMMAND python ${PROJECT_DIR}/scripts/build_default_assets.py ${BUILD_ARGS}
        DEPENDS
            ${SDKCONFIG}
            ${PROJECT_DIR}/scripts/build_default_assets.py
        COMMENT "Building default assets.bin based on configuration"
        VERBATIM
    )
    
    # Create target for generated assets
    add_custom_target(generated_default_assets ALL
        DEPENDS ${GENERATED_ASSETS_BIN}
    )
    
    # Set the generated file path in parent scope
    set(GENERATED_ASSETS_LOCAL_FILE ${GENERATED_ASSETS_BIN} PARENT_SCOPE)
    
    message(STATUS "Default assets build configured: ${GENERATED_ASSETS_BIN}")
endfunction()




partition_table_get_partition_info(size "--partition-name assets" "size")
partition_table_get_partition_info(offset "--partition-name assets" "offset")
if ("${size}" AND "${offset}")
    # Flash assets based on configuration
    # Coglet always flashes the generated default assets (wake word models).
    build_default_assets_bin()
    esptool_py_flash_to_partition(flash "assets" "${GENERATED_ASSETS_LOCAL_FILE}")
    message(STATUS "Generated default assets flash configured: ${GENERATED_ASSETS_LOCAL_FILE} -> assets partition")

    # ---- NMRobotics Coglet: `idf.py flash` resets the web flasher's Settings --
    # Settings saved from the Coglet Updater (wake word, threshold, sounds, AEC)
    # live in one 4 KB sector right before the song library (coglet_settings.h)
    # and take priority over menuconfig. Flashing your own build means "use my
    # menuconfig", so `idf.py flash` writes a blank sector there. Wi-Fi,
    # pairing, reminders and the song library are not touched, and
    # `idf.py app-flash` keeps the settings. The Coglet Updater and the release
    # zips leave this part out (make_manifest.py), so updating keeps them.
    if(CONFIG_COGLET_DANCE AND CONFIG_COGLET_MUSIC)
        math(EXPR coglet_library_bytes "${CONFIG_COGLET_MUSIC_LIBRARY_KB} * 1024")
    else()
        set(coglet_library_bytes 0)
    endif()
    math(EXPR coglet_settings_offset "${offset} + ${size} - ${coglet_library_bytes} - 4096" OUTPUT_FORMAT HEXADECIMAL)
    set(coglet_settings_reset "${CMAKE_BINARY_DIR}/coglet_settings_reset.bin")
    if(NOT EXISTS "${coglet_settings_reset}")
        idf_build_get_property(coglet_python PYTHON)
        execute_process(COMMAND "${coglet_python}" -c
            "import sys; open(sys.argv[1], 'wb').write(b'\\xff' * 4096)" "${coglet_settings_reset}")
    endif()
    esptool_py_flash_target_image(flash coglet_settings_reset "${coglet_settings_offset}" "${coglet_settings_reset}")
    message(STATUS "Coglet: idf.py flash resets the web flasher settings at ${coglet_settings_offset}")
else()
    message(STATUS "Assets partition not found, using v1 partition table")
endif()

/**
 * main.js — Jarvis front-end initialisation & UI event bindings.
 *
 * Handles:
 *   - Page-load setup (call Python init, start Textillate animations)
 *   - Mic / Send / Chat buttons
 *   - Keyboard shortcut  (Ctrl+J)
 *   - Typed message submission
 */

$(document).ready(function () {

  // -----------------------------------------------------------------------
  // 1. Call Python init so the UI sequence can begin
  // -----------------------------------------------------------------------
  try {
    eel.init()();
    console.log("eel.init() called successfully");
  } catch (e) {
    console.log("eel.init() error:", e);
  }

  // -----------------------------------------------------------------------
  // 2. Textillate animations (fail silently if the lib isn't loaded)
  // -----------------------------------------------------------------------
  try {
    $(".text").textillate({
      loop: true,
      speed: 1500,
      sync: true,
      in: { effect: "bounceIn" },
      out: { effect: "bounceOut" },
    });
    $(".siri-message").textillate({
      loop: true,
      sync: true,
      in: { effect: "fadeInUp", sync: true },
      out: { effect: "fadeOutUp", sync: true },
    });
  } catch (e) {
    console.log("Textillate not available");
  }

  // -----------------------------------------------------------------------
  // 3. Mic button — start voice recognition via Python
  // -----------------------------------------------------------------------
  $("#MicBtn").click(function () {
    try {
      eel.play_assistant_sound()();
    } catch (e) {
      /* sound is optional */
    }
    $("#Oval").attr("hidden", true);
    $("#SiriWave").attr("hidden", false);
    eel.takeAllCommands()();
  });

  // -----------------------------------------------------------------------
  // 4. Keyboard shortcut  (Ctrl+J  or  Win+J)
  // -----------------------------------------------------------------------
  $(document).keydown(function (e) {
    if ((e.key === "j" || e.key === "J") && (e.metaKey || e.ctrlKey)) {
      try {
        eel.play_assistant_sound()();
      } catch (err) {
        /* sound is optional */
      }
      $("#Oval").attr("hidden", true);
      $("#SiriWave").attr("hidden", false);
      eel.takeAllCommands()();
    }
  });

  // -----------------------------------------------------------------------
  // 5. Typed commands
  // -----------------------------------------------------------------------
  function sendMessage(message) {
    if (message && message.trim() !== "") {
      $("#Oval").attr("hidden", true);
      $("#SiriWave").attr("hidden", false);
      try {
        eel.takeAllCommands(message.trim())();
      } catch (e) {
        console.log(e);
      }
      $("#chatbox").val("");
      // Trigger input event manually so the Mic/Send button state resets
      $("#chatbox").trigger("input");
    }
  }

  // -- Toggle between mic / send icons as the user types --
  $("#chatbox").on("input", function () {
    var val = $(this).val();
    if (val.length > 0) {
      $("#MicBtn").attr("hidden", true);
      $("#SendBtn").attr("hidden", false);
    } else {
      $("#MicBtn").attr("hidden", false);
      $("#SendBtn").attr("hidden", true);
    }
  });

  // Helper: reset the chatbox buttons to mic mode
  function resetButtons() {
    $("#MicBtn").attr("hidden", false);
    $("#SendBtn").attr("hidden", true);
  }

  // -- Send button --
  $("#SendBtn").click(function () {
    sendMessage($("#chatbox").val());
  });

  // -- Enter key --
  $("#chatbox").keydown(function (e) {
    if (e.key === "Enter") {
      sendMessage($("#chatbox").val());
    }
  });

  // -----------------------------------------------------------------------
  // 6. Chat button — return to main view
  // -----------------------------------------------------------------------
  $("#ChatBtn").click(function () {
    ShowHood();
  });

  // -----------------------------------------------------------------------
  // 7. Settings button — refresh app database
  // -----------------------------------------------------------------------
  $("#SettingBtn").click(function () {
    try {
      eel.play_assistant_sound()();
    } catch (e) {
      /* sound is optional */
    }
    // Show the listening wave as feedback
    $("#Oval").attr("hidden", true);
    $("#SiriWave").attr("hidden", false);
    // Tell user settings are accessible via config.py
    try {
      eel.takeAllCommands("settings")();
    } catch (e) {
      console.log("Settings error:", e);
    }
  });

  console.log("Jarvis ready! Mic button = voice (Python), Chat box = type");
});

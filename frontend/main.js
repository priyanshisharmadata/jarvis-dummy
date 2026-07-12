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
  //    (debounced: ignores clicks while a command is in progress)
  // -----------------------------------------------------------------------
  // Declared with window. so controller.js can release the lock from
  // ShowHood() — otherwise the mic stays blocked until the 15 s timeout.
  window._micBusy = false;
  window._micDebounceTimer = null;

  function _startListening() {
    if (window._micBusy) {
      console.log("Mic busy — ignoring duplicate trigger");
      return;
    }
    window._micBusy = true;

    try {
      eel.play_assistant_sound()();
    } catch (e) {
      /* sound is optional */
    }
    $("#Oval").attr("hidden", true);
    $("#SiriWave").attr("hidden", false);
    eel.takeAllCommands()();

    // Release the lock after a reasonable timeout (Python calls
    // ShowHood() when done, which restores Oval + hides SiriWave)
    clearTimeout(window._micDebounceTimer);
    window._micDebounceTimer = setTimeout(function () {
      window._micBusy = false;
    }, 15000); // 15s — longer than any single voice-command cycle
  }

  $("#MicBtn").click(_startListening);

  // -----------------------------------------------------------------------
  // 4. Keyboard shortcut  (Ctrl+J  or  Win+J)
  // -----------------------------------------------------------------------
  $(document).keydown(function (e) {
    if ((e.key === "j" || e.key === "J") && (e.metaKey || e.ctrlKey)) {
      _startListening();
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
  // 7. Settings button — opens config.py location
  // -----------------------------------------------------------------------
  $("#SettingBtn").click(function () {
    try {
      eel.play_assistant_sound()();
    } catch (e) {
      /* sound is optional */
    }
    // Show brief feedback
    $("#Oval").attr("hidden", true);
    $("#SiriWave").attr("hidden", false);
    try {
      // Refresh app database and show settings info
      eel.takeAllCommands("open settings")();
    } catch (e) {
      console.log("Settings error:", e);
    }
  });

  console.log("Jarvis ready! Mic button = voice (Python), Chat box = type");
});

/**
 * controller.js — Bridge between Python Eel backend and the HTML DOM.
 *
 * These functions are exposed to Python via eel.expose and are the
 * ONLY way the backend updates the UI.  Keep all DOM manipulation here.
 */

/**
 * Update the scrolling message banner.
 * @param {string} message
 */
function DisplayMessage(message) {
  try {
    $(".siri-message li:first").text(message);
    $(".siri-message").textillate("start");
  } catch (e) {
    // Fallback when Textillate isn't loaded
    $(".siri-message li:first").text(message);
  }
}

/**
 * Show the main "hood" / particle UI, hide the wave.
 */
function ShowHood() {
  $("#Oval").attr("hidden", false);
  $("#SiriWave").attr("hidden", true);
}

/**
 * Display the user's message in a chat-bubble style.
 * Falls back to the scrolling message banner when the chat container
 * isn't present in the DOM.
 * @param {string} message
 */
function senderText(message) {
  var chatBox = document.getElementById("chat-canvas-body");
  if (chatBox && message && message.trim() !== "") {
    chatBox.innerHTML +=
      `<div class="row justify-content-end mb-4">
        <div class="width-size">
          <div class="sender_message">${message}</div>
        </div>
      </div>`;
    chatBox.scrollTop = chatBox.scrollHeight;
  } else if (message && message.trim() !== "") {
    // Fallback: show in the scrolling banner
    DisplayMessage("You: " + message);
  }
}

/**
 * Display a received / assistant message in a chat-bubble style.
 * Falls back to the scrolling message banner when the chat container
 * isn't present in the DOM.
 * @param {string} message
 */
function receiverText(message) {
  var chatBox = document.getElementById("chat-canvas-body");
  if (chatBox && message && message.trim() !== "") {
    chatBox.innerHTML +=
      `<div class="row justify-content-start mb-4">
        <div class="width-size">
          <div class="receiver_message">${message}</div>
        </div>
      </div>`;
    chatBox.scrollTop = chatBox.scrollHeight;
  } else if (message && message.trim() !== "") {
    // Fallback: show in the scrolling banner
    DisplayMessage("Jarvis: " + message);
  }
}

// -----------------------------------------------------------------------
//  Loading / authentication sequence helpers
// -----------------------------------------------------------------------

function hideLoader() {
  $("#Loader").attr("hidden", true);
  $("#FaceAuth").attr("hidden", false);
}

function hideFaceAuth() {
  $("#FaceAuth").attr("hidden", true);
  $("#FaceAuthSuccess").attr("hidden", false);
}

function hideFaceAuthSuccess() {
  $("#FaceAuthSuccess").attr("hidden", true);
  $("#HelloGreet").attr("hidden", false);
}

function hideStart() {
  $("#Start").attr("hidden", true);
  setTimeout(function () {
    $("#Oval").addClass("animate__animated animate__zoomIn");
  }, 500);
  setTimeout(function () {
    $("#Oval").attr("hidden", false);
  }, 500);
}

// -----------------------------------------------------------------------
//  Expose functions to Python
// -----------------------------------------------------------------------
$(document).ready(function () {
  eel.expose(DisplayMessage);
  eel.expose(ShowHood);
  eel.expose(senderText);
  eel.expose(receiverText);
  eel.expose(hideLoader);
  eel.expose(hideFaceAuth);
  eel.expose(hideFaceAuthSuccess);
  eel.expose(hideStart);
});

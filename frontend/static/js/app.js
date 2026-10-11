/* ============================================================
   TripGenie — frontend application
   ------------------------------------------------------------
   Backend endpoints:

   POST   /api/travel
          { message, thread_id }

   GET    /api/config
          credential status

   POST   /api/config
          set session keys

   DELETE /api/config
          fall back to server .env

   GET    /health
          server health

   This file is matched to the supplied index.html.
   ============================================================ */

(function () {
  "use strict";

  /* ============================================================
     DOM HELPERS
     ============================================================ */

  function $(id) {
    return document.getElementById(id);
  }

  function createElement(tag, className, text) {
    var node = document.createElement(tag);

    if (className) {
      node.className = className;
    }

    if (text !== undefined && text !== null) {
      node.textContent = text;
    }

    return node;
  }

  function createIcon(pathD, className) {
    var svg = document.createElementNS(
      "http://www.w3.org/2000/svg",
      "svg"
    );

    svg.setAttribute("viewBox", "0 0 24 24");
    svg.setAttribute("fill", "none");
    svg.setAttribute("stroke", "currentColor");
    svg.setAttribute("stroke-width", "2");
    svg.setAttribute("stroke-linecap", "round");
    svg.setAttribute("stroke-linejoin", "round");

    if (className) {
      svg.setAttribute("class", className);
    }

    var path = document.createElementNS(
      "http://www.w3.org/2000/svg",
      "path"
    );

    path.setAttribute("d", pathD);
    svg.appendChild(path);

    return svg;
  }


  /* ============================================================
     DOM REFERENCES
     ============================================================ */

  var conversation = $("conversation");
  var messages = $("messages");

  var hero = $("hero");
  var heroSearch = $("heroSearch");
  var heroInput = $("heroInput");
  var heroPlanBtn = $("heroPlanBtn");

  var composerWrap = document.querySelector(".composer-wrap");
  var composer = $("composer");
  var input = $("input");
  var sendBtn = $("sendBtn");

  var builder = $("builder");
  var builderToggle = $("builderToggle");

  var toastEl = $("toast");

  var statusBtn = $("apiStatus");
  var statusText = statusBtn
    ? statusBtn.querySelector(".status-text")
    : null;

  var setupGate = $("setupGate");
  var gateCreds = $("gateCreds");
  var gateSub = $("gateSub");
  var gateSave = $("gateSave");

  var settingsModal = $("settingsModal");
  var myTripsBtn = $("myTripsBtn");
  var tripsModal = $("tripsModal");
  var tripsScrim = $("tripsScrim");
  var tripsList = $("tripsList");
  var tripsClose = $("tripsClose");

  var accountWrap = $("accountWrap");
  var accountBtn = $("accountBtn");
  var accountDropdown = $("accountDropdown");
  var accountDropdownName = $("accountDropdownName");
  var accountDropdownEmail = $("accountDropdownEmail");
  var accountNameForm = $("accountNameForm");
  var accountNameInput = $("accountNameInput");
  var dropdownMyTrips = $("dropdownMyTrips");
  var dropdownLogout = $("dropdownLogout");

  var accountModal = $("accountModal");
  var accountScrim = $("accountScrim");
  var accountClose = $("accountClose");
  var authTabs = $("authTabs");
  var loginForm = $("loginForm");
  var registerForm = $("registerForm");
  var loginError = $("loginError");
  var registerError = $("registerError");
  var loginSubmit = $("loginSubmit");
  var registerSubmit = $("registerSubmit");

  var currentUser = null;
  var settingsScrim = $("settingsScrim");
  var credList = $("credList");
  var settingsSave = $("settingsSave");


  /* ============================================================
     SAFETY CHECK
     ============================================================ */

  var requiredElements = [
    conversation,
    messages,
    hero,
    heroSearch,
    heroInput,
    heroPlanBtn,
    composer,
    input,
    sendBtn,
    builder,
    builderToggle,
    toastEl,
    statusBtn,
    setupGate,
    gateCreds,
    gateSub,
    gateSave,
    settingsModal,
    settingsScrim,
    credList,
    settingsSave
  ];

  if (requiredElements.some(function (element) {
    return !element;
  })) {
    console.error(
      "TripGenie: One or more required HTML elements are missing."
    );
    return;
  }


  /* ============================================================
     APPLICATION STATE
     ============================================================ */

  var THEME_KEY = "tripgenie.theme";

  var threadId = null;

  var busy = false;

  var config = null;

  var savingConfig = false;


  /* ============================================================
     PROGRESS PIPELINE
     ============================================================ */

  var PHASES = [
    {
      label: "Fetching flights data",
      weight: 0.22
    },
    {
      label: "Searching hotels",
      weight: 0.18
    },
    {
      label: "Checking the weather",
      weight: 0.14
    },
    {
      label: "Building your itinerary",
      weight: 0.23
    },
    {
      label: "Writing your final plan",
      weight: 0.23
    }
  ];

  var ESTIMATED_MS = 55000;


  /* ============================================================
     TOAST
     ============================================================ */

  var toastTimer = null;

  function toast(message) {
    if (!toastEl) {
      return;
    }

    toastEl.textContent = message;
    toastEl.hidden = false;

    requestAnimationFrame(function () {
      toastEl.classList.add("show");
    });

    clearTimeout(toastTimer);

    toastTimer = setTimeout(function () {
      toastEl.classList.remove("show");

      setTimeout(function () {
        toastEl.hidden = true;
      }, 250);
    }, 2800);
  }


  /* ============================================================
     SCROLL
     ============================================================ */

  function scrollToEnd(smooth) {
    requestAnimationFrame(function () {
      conversation.scrollTo({
        top: conversation.scrollHeight,
        behavior: smooth ? "smooth" : "auto"
      });
    });
  }


  /* ============================================================
     THEME
     ============================================================ */

  function initTheme() {
    var stored = null;

    try {
      stored = localStorage.getItem(THEME_KEY);
    } catch (e) {
      stored = null;
    }

    var prefersLight =
      window.matchMedia &&
      window.matchMedia("(prefers-color-scheme: light)").matches;

    var theme =
      stored ||
      (prefersLight ? "light" : "dark");

    document.documentElement.setAttribute(
      "data-theme",
      theme
    );
  }


  $("themeToggle").addEventListener(
    "click",
    function () {
      var current =
        document.documentElement.getAttribute("data-theme");

      var next =
        current === "dark"
          ? "light"
          : "dark";

      document.documentElement.setAttribute(
        "data-theme",
        next
      );

      try {
        localStorage.setItem(
          THEME_KEY,
          next
        );
      } catch (e) {}
    }
  );


  /* ============================================================
     CONFIGURATION
     ============================================================ */

  function isReady() {
    return !!(
      config &&
      config.ready
    );
  }


  function joinAnd(list) {
    if (!list || !list.length) {
      return "";
    }

    if (list.length === 1) {
      return list[0];
    }

    return (
      list.slice(0, -1).join(", ") +
      " and " +
      list[list.length - 1]
    );
  }


  function updateEmptyState() {
    var hasMessages =
      messages.children.length > 0;

    var ready = isReady();

    setupGate.hidden =
      ready || hasMessages;

    hero.classList.toggle(
      "is-hidden",
      !ready || hasMessages
    );

    var featureRow = document.getElementById("featureRow");
    var popularSection = document.querySelector(".popular-section");

    if (featureRow) {
      featureRow.hidden = hasMessages;
    }

    if (popularSection) {
      popularSection.hidden = hasMessages;
    }

    if (composerWrap) {
      /*
       * Only show the bottom composer once a
       * conversation has actually started —
       * before that, the hero search bar is
       * the single entry point, so we don't
       * show two search bars at once.
       */
      composerWrap.hidden = !hasMessages;

      composerWrap.classList.toggle(
        "is-locked",
        !ready
      );
    }

    input.disabled =
      !ready || busy;

    sendBtn.disabled =
      !ready || busy;

    heroInput.disabled =
      !ready || busy;

    heroPlanBtn.disabled =
      !ready || busy;
  }


  function applyConfig(data) {
    config = data;

    var missing =
      (data && data.missing) || [];

    if (data && data.ready) {
      statusBtn.setAttribute(
        "data-state",
        "ok"
      );

      statusText.textContent =
        "API connected";

      statusBtn.title =
        "All keys configured — open settings";
    } else {
      statusBtn.setAttribute(
        "data-state",
        "setup"
      );

      statusText.textContent =
        "No Live API";

      statusBtn.title =
        "No API keys configured — open settings";

      var labels = missing.map(function (name) {
        return (
          data &&
          data.credentials &&
          data.credentials[name] &&
          data.credentials[name].label
        ) || name;
      });

      if (labels.length) {
        gateSub.textContent =
          "The server has no " +
          joinAnd(labels) +
          " configured, so the agents cannot run. Add " +
          (labels.length === 1
            ? "it"
            : "them") +
          " below to start planning.";
      } else {
        gateSub.textContent =
          "The server has no API keys configured, so the agents cannot run. Add them below to start planning.";
      }

      renderCredentials(gateCreds);
    }

    if (!settingsModal.hidden) {
      renderCredentials(credList);
    }

    updateEmptyState();
  }


  function markUnreachable() {
    config = null;

    statusBtn.setAttribute(
      "data-state",
      "down"
    );

    statusText.textContent =
      "API unreachable";

    statusBtn.title =
      "Could not reach the server";

    updateEmptyState();
  }


  function refreshConfig() {
    return fetch(
      "/api/config",
      {
        cache: "no-store"
      }
    )
      .then(function (response) {
        if (!response.ok) {
          throw new Error(
            "HTTP " + response.status
          );
        }

        return response.json();
      })
      .then(function (data) {
        applyConfig(data);
        return data;
      })
      .catch(function (error) {
        console.error(
          "Could not load /api/config:",
          error
        );

        markUnreachable();
        return null;
      });
  }


  /* ============================================================
     CREDENTIALS
     ============================================================ */

  var FIELD_BY_NAME = {
    GROQ_API_KEY: "groq_api_key",
    DATABASE_URL: "database_url"
  };

  var NAME_BY_FIELD = {
    groq_api_key: "GROQ_API_KEY",
    database_url: "DATABASE_URL"
  };


  function renderCredentials(container) {
    container.innerHTML = "";

    if (!config || !config.credentials) {
      container.appendChild(
        createElement(
          "p",
          "cred-loading",
          "Loading…"
        )
      );

      return;
    }

    Object.keys(
      config.credentials
    ).forEach(function (name) {
      var info =
        config.credentials[name];

      var row =
        createElement("div", "cred");

      var head =
        createElement(
          "div",
          "cred-head"
        );

      var label =
        createElement(
          "label",
          "cred-label",
          info.label || name
        );

      head.appendChild(label);

      var badgeText;

      if (info.source === "env") {
        badgeText =
          "From server .env";
      } else if (
        info.source === "session"
      ) {
        badgeText =
          "Set for this session";
      } else {
        badgeText =
          "Not configured";
      }

      var badge =
        createElement(
          "span",
          "badge badge-" +
            (info.source || "missing"),
          badgeText
        );

      head.appendChild(badge);
      row.appendChild(head);

      if (info.hint) {
        row.appendChild(
          createElement(
            "p",
            "cred-hint",
            info.hint
          )
        );
      }

      var field =
        createElement(
          "div",
          "cred-field"
        );

      var box =
        createElement(
          "input",
          "cred-input"
        );

      box.type = "password";

      box.placeholder =
        info.configured
          ? "•••••••• (leave blank to keep)"
          : (
              info.placeholder ||
              "Enter value"
            );

      box.autocomplete = "off";
      box.spellcheck = false;

      box.setAttribute(
        "data-cred",
        name
      );

      field.appendChild(box);

      var reveal =
        createElement(
          "button",
          "icon-btn sm"
        );

      reveal.type = "button";
      reveal.title =
        "Show / hide";

      reveal.setAttribute(
        "aria-label",
        "Show or hide value"
      );

      reveal.appendChild(
        createIcon(
          "M2 12s3.6-7 10-7 10 7 10 7-3.6 7-10 7-10-7-10-7Z"
        )
      );

      reveal.addEventListener(
        "click",
        function () {
          box.type =
            box.type === "password"
              ? "text"
              : "password";
        }
      );

      field.appendChild(reveal);

      row.appendChild(field);

      var error =
        createElement(
          "p",
          "cred-error"
        );

      error.setAttribute(
        "data-error-for",
        name
      );

      error.hidden = true;

      row.appendChild(error);

      container.appendChild(row);
    });
  }


  function openSettings() {
    settingsModal.hidden = false;
    settingsScrim.hidden = false;

    renderCredentials(credList);

    refreshConfig().then(function () {
      renderCredentials(credList);
    });

    var first =
      credList.querySelector(
        ".cred-input"
      );

    if (first) {
      first.focus();
    }
  }


  function closeSettings() {
    settingsModal.hidden = true;
    settingsScrim.hidden = true;
  }


  function setSavingConfig(
    state,
    button
  ) {
    savingConfig = state;

    [settingsSave, gateSave].forEach(
      function (btn) {
        if (btn) {
          btn.disabled = state;
        }
      }
    );

    if (button) {
      button.classList.toggle(
        "is-busy",
        state
      );
    }
  }


  function saveCredentials(
    container,
    button
  ) {
    if (savingConfig) {
      return;
    }

    var payload = {};
    var anything = false;

    container
      .querySelectorAll(".cred-input")
      .forEach(function (box) {
        var value =
          box.value.trim();

        if (!value) {
          return;
        }

        var credentialName =
          box.getAttribute(
            "data-cred"
          );

        var field =
          FIELD_BY_NAME[
            credentialName
          ];

        if (!field) {
          return;
        }

        payload[field] = value;
        anything = true;
      });

    container
      .querySelectorAll(".cred-error")
      .forEach(function (node) {
        node.hidden = true;
        node.textContent = "";
      });

    if (!anything) {
      toast(
        "Enter a key first."
      );

      var empty =
        container.querySelector(
          ".cred-input"
        );

      if (empty) {
        empty.focus();
      }

      return;
    }

    setSavingConfig(
      true,
      button
    );

    fetch(
      "/api/config",
      {
        method: "POST",
        headers: {
          "Content-Type":
            "application/json"
        },
        body: JSON.stringify(payload)
      }
    )
      .then(function (response) {
        return response
          .json()
          .catch(function () {
            return {
              success: false,
              error:
                "Server returned invalid JSON."
            };
          })
          .then(function (data) {
            return {
              ok: response.ok,
              status: response.status,
              data: data
            };
          });
      })
      .then(function (result) {
        var data =
          result.data || {};

        if (
          !result.ok ||
          data.success === false
        ) {
          var errors =
            data.errors || {};

          var shown = 0;

          Object.keys(errors).forEach(
            function (field) {
              var name =
                NAME_BY_FIELD[field];

              if (!name) {
                return;
              }

              var errorNode =
                container.querySelector(
                  '[data-error-for="' +
                    name +
                    '"]'
                );

              if (errorNode) {
                errorNode.textContent =
                  errors[field];

                errorNode.hidden =
                  false;

                shown++;
              }
            }
          );

          toast(
            shown
              ? "Check the highlighted field."
              : (
                  data.error ||
                  "Could not save."
                )
          );

          return;
        }

        applyConfig(data);

        renderCredentials(
          container
        );

        toast(
          data.ready
            ? "Connected."
            : "Saved — one key still missing."
        );
      })
      .catch(function (error) {
        console.error(
          "Credential save failed:",
          error
        );

        toast(
          "Could not reach the server."
        );
      })
      .then(function () {
        setSavingConfig(
          false,
          button
        );
      });
  }


  function resetSettings() {
    if (savingConfig) {
      return;
    }

    setSavingConfig(
      true,
      settingsSave
    );

    fetch(
      "/api/config",
      {
        method: "DELETE"
      }
    )
      .then(function (response) {
        if (!response.ok) {
          throw new Error(
            "HTTP " +
              response.status
          );
        }

        return response.json();
      })
      .then(function (data) {
        applyConfig(data);

        renderCredentials(
          credList
        );

        toast(
          "Session keys cleared."
        );
      })
      .catch(function (error) {
        console.error(
          "Reset failed:",
          error
        );

        toast(
          "Could not reach the server."
        );
      })
      .then(function () {
        setSavingConfig(
          false,
          settingsSave
        );
      });
  }


  /* ============================================================
     SETTINGS EVENTS
     ============================================================ */

  $("settingsBtn").addEventListener(
    "click",
    openSettings
  );

  statusBtn.addEventListener(
    "click",
    openSettings
  );

  $("settingsClose").addEventListener(
    "click",
    closeSettings
  );

  settingsScrim.addEventListener(
    "click",
    closeSettings
  );

  settingsSave.addEventListener(
    "click",
    function () {
      saveCredentials(
        credList,
        settingsSave
      );
    }
  );

  gateSave.addEventListener(
    "click",
    function () {
      saveCredentials(
        gateCreds,
        gateSave
      );
    }
  );

  $("settingsReset").addEventListener(
    "click",
    resetSettings
  );


  document.addEventListener(
    "keydown",
    function (event) {
      if (
        event.key === "Escape" &&
        !settingsModal.hidden
      ) {
        closeSettings();
      }
    }
  );


  /* ============================================================
     TEXT CONVERSION
     ============================================================ */

  function toText(value) {
    if (
      value === null ||
      value === undefined
    ) {
      return "";
    }

    if (typeof value === "string") {
      return value;
    }

    if (
      typeof value === "number" ||
      typeof value === "boolean"
    ) {
      return String(value);
    }

    if (Array.isArray(value)) {
      return value
        .map(toText)
        .filter(Boolean)
        .join("\n\n");
    }

    if (typeof value === "object") {
      if (
        typeof value.text === "string"
      ) {
        return value.text;
      }

      if (
        typeof value.content === "string"
      ) {
        return value.content;
      }

      if (
        Array.isArray(value.content)
      ) {
        return toText(
          value.content
        );
      }

      try {
        return (
          "```json\n" +
          JSON.stringify(
            value,
            null,
            2
          ) +
          "\n```"
        );
      } catch (e) {
        return String(value);
      }
    }

    return String(value);
  }


  /* ============================================================
     MARKDOWN BLOCK
     ============================================================ */

  function mdBlock(
    source,
    emptyText
  ) {
    var box =
      createElement(
        "div",
        "md"
      );

    var text =
      toText(source).trim();

    if (!text) {
      var empty =
        createElement(
          "div",
          "md-empty"
        );

      empty.appendChild(
        createIcon(
          "M12 9v4M12 17h.01M10.3 3.9 1.8 18a2 2 0 0 0 1.7 3h17a2 2 0 0 0 1.7-3L13.7 3.9a2 2 0 0 0-3.4 0Z"
        )
      );

      empty.appendChild(
        createElement(
          "span",
          null,
          emptyText ||
            "No data returned for this section."
        )
      );

      box.appendChild(empty);

      return box;
    }

    if (
      window.MD &&
      typeof window.MD.render ===
        "function"
    ) {
      box.innerHTML =
        window.MD.render(text);
    } else {
      box.textContent = text;
    }

    return box;
  }


  /* ============================================================
     USER MESSAGE
     ============================================================ */

  function renderUser(text) {
    var wrapper =
      createElement(
        "div",
        "msg msg-user"
      );

    wrapper.appendChild(
      createElement(
        "div",
        "bubble-user",
        text
      )
    );

    messages.appendChild(
      wrapper
    );

    return wrapper;
  }


  /* ============================================================
     TOOL BUTTON
     ============================================================ */

  function toolButton(
    label,
    pathD,
    handler
  ) {
    var button =
      createElement(
        "button",
        "icon-btn sm"
      );

    button.type = "button";
    button.title = label;

    button.setAttribute(
      "aria-label",
      label
    );

    button.appendChild(
      createIcon(pathD)
    );

    button.addEventListener(
      "click",
      handler
    );

    return button;
  }


  /* ============================================================
     PLAN TEXT
     ============================================================ */

  function plainTextOf(result) {
    var title =
      result.__query ||
      "Trip plan";

    var answer =
      toText(result.answer);

    return [
      "# " + title,
      "",
      answer
    ].join("\n");
  }


  /* ============================================================
     COPY
     ============================================================ */

  function copyText(text) {
    if (
      navigator.clipboard &&
      navigator.clipboard.writeText
    ) {
      return navigator.clipboard.writeText(
        text
      );
    }

    return new Promise(
      function (resolve, reject) {
        var textarea =
          document.createElement(
            "textarea"
          );

        textarea.value = text;
        textarea.style.position =
          "fixed";
        textarea.style.left =
          "-9999px";

        document.body.appendChild(
          textarea
        );

        textarea.select();

        try {
          var success =
            document.execCommand(
              "copy"
            );

          document.body.removeChild(
            textarea
          );

          if (success) {
            resolve();
          } else {
            reject(
              new Error(
                "Copy failed"
              )
            );
          }
        } catch (error) {
          document.body.removeChild(
            textarea
          );

          reject(error);
        }
      }
    );
  }


  /* ============================================================
     RENDER FINAL RESULT
     ============================================================ */

  function renderResult(result) {
    var card =
      createElement(
        "article",
        "card"
      );


    /* ---------------- CARD HEADER ---------------- */

    var head =
      createElement(
        "div",
        "card-head"
      );

    var avatar =
      createElement(
        "div",
        "card-avatar"
      );

    avatar.appendChild(
      createIcon(
        "M17.8 19.2 16 11l3.5-3.5a2.1 2.1 0 0 0-3-3L13 8 4.8 6.2a.8.8 0 0 0-.8 1.3L8 11l-2 2-2.2-.5a.6.6 0 0 0-.6 1L5 16l2.5 1.8a.6.6 0 0 0 1-.6L8 15l2-2 3.5 4a.8.8 0 0 0 1.3-.8Z"
      )
    );

    head.appendChild(
      avatar
    );


    var titleBox =
      createElement(
        "div",
        "card-title"
      );

    titleBox.appendChild(
      createElement(
        "strong",
        null,
        "TripGenie AI"
      )
    );

    titleBox.appendChild(
      createElement(
        "small",
        null,
        "Plan ready"
      )
    );

    head.appendChild(
      titleBox
    );


    /* ---------------- CARD TOOLS ---------------- */

    var tools =
      createElement(
        "div",
        "card-tools"
      );


    /* COPY */

    tools.appendChild(
      toolButton(
        "Copy plan",
        "M8 4h10a2 2 0 0 1 2 2v10M16 8H6a2 2 0 0 0-2 2v10a2 2 0 0 0 2 2h10a2 2 0 0 0 2-2V10a2 2 0 0 0-2-2Z",
        function () {
          var text =
            plainTextOf(
              result
            );

          copyText(text)
            .then(function () {
              toast(
                "Plan copied to clipboard"
              );
            })
            .catch(function () {
              toast(
                "Could not copy"
              );
            });
        }
      )
    );


    /* DOWNLOAD */

    tools.appendChild(
      toolButton(
        "Download as Markdown",
        "M12 3v12m0 0 4-4m-4 4-4-4M4 17v2a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2v-2",
        function () {
          var blob =
            new Blob(
              [
                plainTextOf(
                  result
                )
              ],
              {
                type:
                  "text/markdown;charset=utf-8"
              }
            );

          var url =
            URL.createObjectURL(
              blob
            );

          var link =
            document.createElement(
              "a"
            );

          link.href = url;
          link.download =
            "tripgenie-plan.md";

          document.body.appendChild(
            link
          );

          link.click();

          document.body.removeChild(
            link
          );

          setTimeout(
            function () {
              URL.revokeObjectURL(
                url
              );
            },
            1000
          );
        }
      )
    );


    /* PRINT */

    tools.appendChild(
      toolButton(
        "Print",
        "M6 9V3h12v6M6 18H4a2 2 0 0 1-2-2v-4a2 2 0 0 1 2-2h16a2 2 0 0 1 2 2v4h-2M6 14h12v7H6z",
        function () {
          window.print();
        }
      )
    );


    head.appendChild(
      tools
    );

    card.appendChild(
      head
    );


    /* ---------------- CARD BODY ---------------- */

    var body =
      createElement(
        "div",
        "card-body"
      );

    body.appendChild(
      mdBlock(
        result.answer,
        "The agent returned an empty response."
      )
    );

    card.appendChild(
      body
    );


    /* ---------------- MESSAGE WRAPPER ---------------- */

    var wrapper =
      createElement(
        "div",
        "msg"
      );

    wrapper.appendChild(
      card
    );

    messages.appendChild(
      wrapper
    );

    return wrapper;
  }


  /* ============================================================
     BUDGET CARD
     ============================================================ */

  function formatMoney(currency, amount) {
    if (amount === null || amount === undefined || isNaN(Number(amount))) {
      return "—";
    }

    var value = Number(amount);
    var formatted;

    try {
      formatted = value.toLocaleString();
    } catch (e) {
      formatted = String(value);
    }

    return (currency || "USD") + " " + formatted;
  }

  function budgetBarRow(label, amount, currency, maxAmount) {
    var row = createElement("div", "budget-row");

    row.appendChild(
      createElement("span", "budget-row-label", label)
    );

    var track = createElement("div", "budget-bar-track");
    var fill = createElement("div", "budget-bar-fill");

    var pct = 0;

    if (maxAmount && !isNaN(Number(amount)) && Number(amount) > 0) {
      pct = Math.min(100, (Number(amount) / maxAmount) * 100);
    }

    fill.style.width = pct + "%";
    track.appendChild(fill);
    row.appendChild(track);

    row.appendChild(
      createElement("span", "budget-row-value", formatMoney(currency, amount))
    );

    return row;
  }

  function renderBudgetCard(budget) {
    var card = createElement("article", "card budget-card");

    /* ---- header ---- */

    var head = createElement("div", "card-head");

    var avatar = createElement("div", "card-avatar");
    avatar.appendChild(
      createIcon("M3 3v18h18M18 17V9M13 17V5M8 17v-3")
    );
    head.appendChild(avatar);

    var titleBox = createElement("div", "card-title");
    titleBox.appendChild(createElement("strong", null, "Budget Breakdown"));
    titleBox.appendChild(createElement("small", null, "Estimated cost for this trip"));
    head.appendChild(titleBox);

    card.appendChild(head);

    /* ---- body ---- */

    var body = createElement("div", "card-body");

    var currency = budget.currency || "USD";
    var flights = budget.flights;
    var hotels = budget.hotels;
    var attractions = budget.attractions;
    var total = budget.total;
    var userBudget = budget.user_budget;
    var status = budget.status || "unknown";
    var note = budget.note;

    var hasNumbers =
      [flights, hotels, attractions, total].some(function (v) {
        return v !== null && v !== undefined && !isNaN(Number(v));
      });

    if (hasNumbers) {
      var maxAmount = Math.max(
        Number(flights) || 0,
        Number(hotels) || 0,
        Number(attractions) || 0
      ) || 1;

      var rows = createElement("div", "budget-rows");
      rows.appendChild(budgetBarRow("Flights", flights, currency, maxAmount));
      rows.appendChild(budgetBarRow("Hotels", hotels, currency, maxAmount));
      rows.appendChild(budgetBarRow("Attractions", attractions, currency, maxAmount));
      body.appendChild(rows);

      var totalRow = createElement("div", "budget-total-row");
      totalRow.appendChild(createElement("span", null, "Estimated Total"));
      totalRow.appendChild(createElement("strong", null, formatMoney(currency, total)));
      body.appendChild(totalRow);

      if (userBudget !== null && userBudget !== undefined) {
        var compare = createElement("div", "budget-compare");

        var badgeClass =
          status === "over_budget"
            ? "badge budget-badge-over"
            : status === "within_budget"
              ? "badge budget-badge-within"
              : "badge budget-badge-unknown";

        var badgeText =
          status === "over_budget"
            ? "Over your budget"
            : status === "within_budget"
              ? "Within your budget"
              : "Budget comparison unavailable";

        compare.appendChild(createElement("span", badgeClass, badgeText));

        compare.appendChild(
          createElement(
            "span",
            "budget-user-amount",
            "Your budget: " + formatMoney(currency, userBudget)
          )
        );

        body.appendChild(compare);
      }
    }

    if (note) {
      body.appendChild(createElement("p", "budget-note", note));
    }

    if (!hasNumbers && !note) {
      body.appendChild(
        createElement("p", "budget-note", "No budget estimate available for this trip.")
      );
    }

    card.appendChild(body);

    var wrapper = createElement("div", "msg");
    wrapper.appendChild(card);
    messages.appendChild(wrapper);

    return wrapper;
  }


  /* ============================================================
     ROUTE MAP CARD
     ============================================================ */

  var _routeMapCounter = 0;

  var ROUTE_MAP_COLORS = [
    "#2479f4", "#e11d48", "#16a34a", "#f59e0b",
    "#7657d9", "#12a3b8", "#d946ef", "#64748b"
  ];

  function renderRouteMapCard(routePlan) {
    if (!window.L) {
      console.warn("Leaflet did not load - skipping route map.");
      return;
    }

    var days = (routePlan && routePlan.days) || [];

    var hasAnyPlace = days.some(function (day) {
      return day.places && day.places.length;
    });

    if (!hasAnyPlace) {
      return;
    }

    _routeMapCounter += 1;
    var containerId = "routeMap" + _routeMapCounter;

    var card = createElement("article", "card route-map-card");

    var head = createElement("div", "card-head");
    var avatar = createElement("div", "card-avatar");
    avatar.appendChild(
      createIcon("M20 10c0 5-8 12-8 12S4 15 4 10a8 8 0 1 1 16 0Z")
    );
    head.appendChild(avatar);

    var titleBox = createElement("div", "card-title");
    titleBox.appendChild(createElement("strong", null, "Trip Route Map"));
    titleBox.appendChild(createElement("small", null, "Attractions grouped by day"));
    head.appendChild(titleBox);

    card.appendChild(head);

    var body = createElement("div", "card-body");

    var mapContainer = createElement("div", "route-map-container");
    mapContainer.id = containerId;
    body.appendChild(mapContainer);

    var legend = createElement("div", "route-map-legend");

    days.forEach(function (day, index) {
      if (!day.places || !day.places.length) {
        return;
      }

      var color = ROUTE_MAP_COLORS[index % ROUTE_MAP_COLORS.length];

      var item = createElement("span", "route-map-legend-item");
      var swatch = createElement("span", "route-map-swatch");
      swatch.style.background = color;

      item.appendChild(swatch);
      item.appendChild(document.createTextNode("Day " + day.day));
      legend.appendChild(item);
    });

    body.appendChild(legend);

    if (routePlan.unplaced && routePlan.unplaced.length) {
      var unplacedNote = createElement(
        "p",
        "route-map-unplaced",
        "Couldn't place on the map: " + routePlan.unplaced.join(", ")
      );

      body.appendChild(unplacedNote);
    }

    card.appendChild(body);

    var wrapper = createElement("div", "msg");
    wrapper.appendChild(card);
    messages.appendChild(wrapper);

    requestAnimationFrame(function () {
      try {
        var map = L.map(containerId, { scrollWheelZoom: false });

        L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
          attribution: "&copy; OpenStreetMap contributors",
          maxZoom: 19
        }).addTo(map);

        var allLatLngs = [];

        days.forEach(function (day, index) {
          if (!day.places || !day.places.length) {
            return;
          }

          var color = ROUTE_MAP_COLORS[index % ROUTE_MAP_COLORS.length];
          var dayLatLngs = [];

          day.places.forEach(function (place) {
            var latlng = [place.lat, place.lon];
            dayLatLngs.push(latlng);
            allLatLngs.push(latlng);

            var icon = L.divIcon({
              className: "route-map-marker",
              html:
                '<span style="background:' + color + '">' +
                '<svg viewBox="0 0 24 24" fill="white" width="14" height="14">' +
                '<path d="M12 2C8.13 2 5 5.13 5 9c0 5.25 7 13 7 13s7-7.75 7-13c0-3.87-3.13-7-7-7zm0 9.5A2.5 2.5 0 1 1 12 6.5a2.5 2.5 0 0 1 0 5z"/>' +
                "</svg>" +
                "</span>",
              iconSize: [28, 28],
              iconAnchor: [14, 28]
            });

            L.marker(latlng, { icon: icon })
              .addTo(map)
              .bindPopup("<strong>" + place.name + "</strong><br>Day " + day.day);
          });

          if (dayLatLngs.length > 1) {
            L.polyline(dayLatLngs, { color: color, weight: 3, opacity: 0.6 }).addTo(map);
          }
        });

        if (allLatLngs.length) {
          map.fitBounds(allLatLngs, { padding: [30, 30] });
        }
      } catch (error) {
        console.error("Failed to render route map:", error);
      }
    });

    return wrapper;
  }


  /* ============================================================
     PACKING CARD
     ============================================================ */

  function renderPackingCard(packing) {
    var categories = (packing && packing.categories) || [];

    if (!categories.length) {
      return;
    }

    var card = createElement("article", "card packing-card");

    var head = createElement("div", "card-head");
    var avatar = createElement("div", "card-avatar");
    avatar.appendChild(
      createIcon("M20 7h-3V6a4 4 0 0 0-8 0v1H6a2 2 0 0 0-2 2v9a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2V9a2 2 0 0 0-2-2ZM11 6a1 1 0 0 1 2 0v1h-2Z")
    );
    head.appendChild(avatar);

    var titleBox = createElement("div", "card-title");
    titleBox.appendChild(createElement("strong", null, "Packing List"));
    titleBox.appendChild(createElement("small", null, "Tap an item to check it off"));
    head.appendChild(titleBox);

    card.appendChild(head);

    var body = createElement("div", "card-body");

    categories.forEach(function (category) {
      if (!category.items || !category.items.length) {
        return;
      }

      body.appendChild(createElement("h4", "packing-category", category.name));

      var list = createElement("ul", "packing-list");

      category.items.forEach(function (itemText) {
        var li = createElement("li", "packing-item", itemText);

        li.addEventListener("click", function () {
          li.classList.toggle("is-checked");
        });

        list.appendChild(li);
      });

      body.appendChild(list);
    });

    if (packing.note) {
      body.appendChild(createElement("p", "packing-note", packing.note));
    }

    card.appendChild(body);

    var wrapper = createElement("div", "msg");
    wrapper.appendChild(card);
    messages.appendChild(wrapper);

    return wrapper;
  }


  /* ============================================================
     MY TRIPS
     ============================================================ */

  function openTrips() {
    if (!tripsModal || !tripsList) { return; }

    tripsModal.hidden = false;
    tripsScrim.hidden = false;
    tripsList.innerHTML = '<p class="cred-loading">Loading…</p>';

    fetch("/api/trips", { cache: "no-store" })
      .then(function (r) { return r.json(); })
      .then(function (data) {
        renderTripsList(data.trips || []);
      })
      .catch(function () {
        tripsList.innerHTML = '<p class="cred-loading">Could not load trips.</p>';
      });
  }

  function closeTrips() {
    if (!tripsModal) { return; }
    tripsModal.hidden = true;
    tripsScrim.hidden = true;
  }

  function renderTripsList(trips) {
    tripsList.innerHTML = "";

    if (!trips.length) {
      tripsList.appendChild(createElement("p", "cred-loading", "No saved trips yet."));
      return;
    }

    trips.forEach(function (trip) {
      var row = createElement("div", "trip-row");

      var open = createElement("button", "trip-row-open");
      open.type = "button";

      var when = new Date(trip.created_at);
      var whenText = isNaN(when.getTime()) ? "" : when.toLocaleDateString();

      open.appendChild(createElement("strong", null, trip.query));
      open.appendChild(createElement("small", null, whenText));

      open.addEventListener("click", function () {
        openSavedTrip(trip.id);
      });

      row.appendChild(open);

      var del = createElement("button", "icon-btn sm");
      del.type = "button";
      del.title = "Delete";
      del.appendChild(createIcon("M6 6 18 18M6 18 18 6"));

      del.addEventListener("click", function (event) {
        event.stopPropagation();

        fetch("/api/trips/" + trip.id, { method: "DELETE" })
          .then(function () { row.remove(); });
      });

      row.appendChild(del);
      tripsList.appendChild(row);
    });
  }

  function openSavedTrip(tripId) {
    fetch("/api/trips/" + tripId)
      .then(function (r) {
        if (!r.ok) { throw new Error("Not found"); }
        return r.json();
      })
      .then(function (trip) {
        closeTrips();

        messages.innerHTML = "";
        threadId = trip.thread_id;

        renderUser(trip.query);
        renderResult({ answer: trip.answer, __query: trip.query });

        updateEmptyState();
        scrollToEnd(false);
      })
      .catch(function () {
        toast("Could not open that trip.");
      });
  }

  if (myTripsBtn) {
    myTripsBtn.addEventListener("click", openTrips);
  }

  if (tripsClose) {
    tripsClose.addEventListener("click", closeTrips);
  }

  if (tripsScrim) {
    tripsScrim.addEventListener("click", closeTrips);
  }


  /* ============================================================
     ACCOUNT / AUTH
     ============================================================ */

  function openAccount() {
    if (!accountModal) { return; }
    accountModal.hidden = false;
    accountScrim.hidden = false;
  }

  function closeAccount() {
    if (!accountModal) { return; }
    accountModal.hidden = true;
    accountScrim.hidden = true;
  }

  function openDropdown() {
    if (!accountDropdown) { return; }

    accountDropdownName.textContent = currentUser.display_name;
    accountDropdownEmail.textContent = currentUser.email;
    accountNameInput.value = currentUser.display_name;

    accountDropdown.hidden = false;
  }

  function closeDropdown() {
    if (accountDropdown) {
      accountDropdown.hidden = true;
    }
  }

  function updateAccountButton() {
    if (!accountBtn) { return; }

    if (currentUser) {
      accountBtn.classList.add("is-logged-in");
      accountBtn.title = currentUser.email;
    } else {
      accountBtn.classList.remove("is-logged-in");
      accountBtn.title = "Log in";
      closeDropdown();
    }
  }

  function refreshCurrentUser() {
    return fetch("/api/auth/me", { cache: "no-store" })
      .then(function (r) { return r.json(); })
      .then(function (data) {
        currentUser = data.user || null;
        updateAccountButton();
      })
      .catch(function () {});
  }

  if (accountBtn) {
    accountBtn.addEventListener("click", function (event) {
      event.stopPropagation();

      if (currentUser) {
        if (accountDropdown.hidden) {
          openDropdown();
        } else {
          closeDropdown();
        }
      } else {
        openAccount();
      }
    });
  }

  document.addEventListener("click", function (event) {
    if (
      accountDropdown &&
      !accountDropdown.hidden &&
      accountWrap &&
      !accountWrap.contains(event.target)
    ) {
      closeDropdown();
    }
  });

  if (dropdownLogout) {
    dropdownLogout.addEventListener("click", function () {
      fetch("/api/auth/logout", { method: "POST" })
        .then(function () {
          currentUser = null;
          updateAccountButton();
          toast("Logged out.");
        });
    });
  }

  if (dropdownMyTrips) {
    dropdownMyTrips.addEventListener("click", function () {
      closeDropdown();
      openTrips();
    });
  }

  if (accountNameForm) {
    accountNameForm.addEventListener("submit", function (event) {
      event.preventDefault();

      var newName = accountNameInput.value.trim();
      if (!newName) { return; }

      fetch("/api/auth/profile", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ display_name: newName })
      })
        .then(function (r) { return r.json(); })
        .then(function (data) {
          if (data.success) {
            currentUser = data.user;
            accountDropdownName.textContent = currentUser.display_name;
            toast("Name updated.");
          } else {
            toast(data.error || "Could not update name.");
          }
        })
        .catch(function () {
          toast("Could not reach the server.");
        });
    });
  }

  if (accountClose) { accountClose.addEventListener("click", closeAccount); }
  if (accountScrim) { accountScrim.addEventListener("click", closeAccount); }

  if (authTabs) {
    authTabs.addEventListener("click", function (event) {
      var tabBtn = event.target.closest(".auth-tab");
      if (!tabBtn) { return; }

      var tab = tabBtn.getAttribute("data-tab");

      authTabs.querySelectorAll(".auth-tab").forEach(function (t) {
        t.classList.toggle("is-active", t === tabBtn);
      });

      loginForm.hidden = tab !== "login";
      registerForm.hidden = tab !== "register";
    });
  }

  function setFormBusy(button, errorEl, state) {
    button.classList.toggle("is-busy", state);
    button.disabled = state;
    if (!state && errorEl) { errorEl.hidden = true; }
  }

  if (loginForm) {
    loginForm.addEventListener("submit", function (event) {
      event.preventDefault();

      setFormBusy(loginSubmit, loginError, true);

      fetch("/api/auth/login", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          email: $("loginEmail").value,
          password: $("loginPassword").value
        })
      })
        .then(function (r) { return r.json().then(function (data) { return { ok: r.ok, data: data }; }); })
        .then(function (result) {
          if (!result.ok) {
            loginError.textContent = result.data.error || "Could not log in.";
            loginError.hidden = false;
            return;
          }

          currentUser = result.data.user;
          updateAccountButton();
          closeAccount();
          toast("Welcome back, " + currentUser.display_name + "!");
          loginForm.reset();
        })
        .catch(function () {
          loginError.textContent = "Could not reach the server.";
          loginError.hidden = false;
        })
        .then(function () {
          setFormBusy(loginSubmit, null, false);
        });
    });
  }

  if (registerForm) {
    registerForm.addEventListener("submit", function (event) {
      event.preventDefault();

      setFormBusy(registerSubmit, registerError, true);

      fetch("/api/auth/register", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          email: $("registerEmail").value,
          password: $("registerPassword").value,
          display_name: $("registerName").value
        })
      })
        .then(function (r) { return r.json().then(function (data) { return { ok: r.ok, data: data }; }); })
        .then(function (result) {
          if (!result.ok) {
            registerError.textContent = result.data.error || "Could not create account.";
            registerError.hidden = false;
            return;
          }

          currentUser = result.data.user;
          updateAccountButton();
          closeAccount();
          toast("Account created — welcome, " + currentUser.display_name + "!");
          registerForm.reset();
        })
        .catch(function () {
          registerError.textContent = "Could not reach the server.";
          registerError.hidden = false;
        })
        .then(function () {
          setFormBusy(registerSubmit, null, false);
        });
    });
  }


  /* ============================================================
     ERROR CARD
     ============================================================ */

  function renderError(
    message,
    kind
  ) {
    var card =
      createElement(
        "article",
        "card error-card"
      );

    var body =
      createElement(
        "div",
        "error-body"
      );

    body.appendChild(
      createIcon(
        "M12 9v4M12 17h.01M10.3 3.9 1.8 18a2 2 0 0 0 1.7 3h17a2 2 0 0 0 1.7-3L13.7 3.9a2 2 0 0 0-3.4 0Z",
        "error-ico"
      )
    );


    var messagesByKind = {
      server: {
        title:
          "The planner could not finish",

        detail:
          "The request reached the server but the agent run failed. Check your backend/uvicorn console for the full traceback."
      },

      network: {
        title:
          "Could not reach the server",

        detail:
          "The request never completed. Check that the server is running and that the frontend is being served from the correct backend."
      },

      render: {
        title:
          "The plan came back, but could not be displayed",

        detail:
          "The server returned data, but the frontend could not render it."
      },

      setup: {
        title:
          "Missing credentials",

        detail:
          "Add the required API keys in Settings, or configure them in the server's .env file."
      }
    };


    var copy =
      messagesByKind[
        kind || "server"
      ] ||
      messagesByKind.server;


    var textBox =
      createElement("div");


    textBox.appendChild(
      createElement(
        "strong",
        null,
        copy.title
      )
    );

    textBox.appendChild(
      createElement(
        "p",
        null,
        copy.detail
      )
    );

    if (message) {
      textBox.appendChild(
        createElement(
          "code",
          null,
          message
        )
      );
    }


    if (kind === "setup") {
      var open =
        createElement(
          "button",
          "btn btn-soft btn-sm",
          "Open settings"
        );

      open.type = "button";

      open.addEventListener(
        "click",
        openSettings
      );

      textBox.appendChild(
        open
      );
    }


    body.appendChild(
      textBox
    );

    card.appendChild(
      body
    );


    var wrapper =
      createElement(
        "div",
        "msg"
      );

    wrapper.appendChild(
      card
    );

    messages.appendChild(
      wrapper
    );

    return wrapper;
  }


  /* ============================================================
     LOADING PIPELINE
     ============================================================ */

    var STEP_DEFINITIONS = [
    { node: "flight_agent", label: "Fetching flights" },
    { node: "hotel_agent", label: "Searching hotels" },
    { node: "attraction_agent", label: "Finding attractions" },
    { node: "route_agent", label: "Planning your route" },
    { node: "weather_agent", label: "Checking the weather" },
    { node: "itinerary_agent", label: "Building your itinerary" },
    { node: "packing_agent", label: "Preparing your packing list" },
    { node: "budget_agent", label: "Estimating your budget" },
    { node: "final_agent", label: "Writing your final plan" }
  ];

  function renderPipeline() {
    var card =
      createElement(
        "article",
        "card progress-card"
      );

    var head =
      createElement(
        "div",
        "progress-head"
      );

    var label =
      createElement(
        "span",
        "progress-label",
        "Planning your trip…"
      );

    head.appendChild(label);
    card.appendChild(head);

    var list =
      createElement(
        "ul",
        "pipeline-list"
      );

    var rowsByNode = {};

    STEP_DEFINITIONS.forEach(function (step) {
      var li = createElement("li", "pipeline-step is-pending");
      var icon = createElement("span", "pipeline-icon");
      var stepLabel = createElement("span", "pipeline-step-label", step.label);

      li.appendChild(icon);
      li.appendChild(stepLabel);
      list.appendChild(li);

      rowsByNode[step.node] = li;
    });

    card.appendChild(list);

    var wrapper =
      createElement(
        "div",
        "msg"
      );

    wrapper.appendChild(card);
    messages.appendChild(wrapper);

    var currentIndex = -1;

    function activate(nodeName) {
      var row = rowsByNode[nodeName];

      if (row) {
        row.classList.remove("is-pending");
        row.classList.add("is-active");
      }
    }

    function markStep(nodeName) {
      var row = rowsByNode[nodeName];

      if (!row) {
        return;
      }

      row.classList.remove("is-pending", "is-active");
      row.classList.add("is-done");

      var stepIndex = -1;

      for (var i = 0; i < STEP_DEFINITIONS.length; i++) {
        if (STEP_DEFINITIONS[i].node === nodeName) {
          stepIndex = i;
          break;
        }
      }

      if (stepIndex > currentIndex) {
        currentIndex = stepIndex;

        var next = STEP_DEFINITIONS[stepIndex + 1];

        if (next) {
          activate(next.node);
        }
      }
    }

    if (STEP_DEFINITIONS[0]) {
      activate(STEP_DEFINITIONS[0].node);
    }

    return {
      node: wrapper,

      markStep: markStep,

      finish: function () {
        STEP_DEFINITIONS.forEach(function (step) {
          var row = rowsByNode[step.node];

          if (row) {
            row.classList.remove("is-pending", "is-active");
            row.classList.add("is-done");
          }
        });

        label.textContent = "Trip plan ready";
      }
    };
  } 


  /* ============================================================
     BUSY STATE
     ============================================================ */

  function setBusy(state) {
    busy = state;

    sendBtn.classList.toggle(
      "is-busy",
      state
    );

    heroPlanBtn.classList.toggle(
      "is-busy",
      state
    );

    updateEmptyState();
  }


  /* ============================================================
     SEND TRIP REQUEST
     ============================================================ */

    function send(text) {
    if (busy) {
      return;
    }

    var message = String(text !== undefined && text !== null ? text : input.value).trim();

    if (!message) {
      toast("Tell me where you want to go first.");
      return;
    }

    if (!isReady()) {
      toast("No live API — add your keys first.");
      updateEmptyState();
      return;
    }

    input.value = "";
    autosize();
    setBusy(true);

    renderUser(message);
    updateEmptyState();

    var pipeline = renderPipeline();
    scrollToEnd(true);

    /* Backend request — streamed, so the pipeline above fills in live */

    var finished = false;

    function cleanupPipeline() {
      pipeline.finish();

      if (pipeline.node.parentNode) {
        pipeline.node.remove();
      }
    }

    function handleFailure(errorMessage, kind) {
      if (finished) { return; }
      finished = true;

      cleanupPipeline();

      renderError(errorMessage, kind || "server");

      scrollToEnd(true);

      /* Refresh credentials — the server may have reported a config problem. */
      refreshConfig();

      setBusy(false);
      input.focus();
    }

    function handleSuccess(data) {
      if (finished) { return; }
      finished = true;

      cleanupPipeline();

      data.__query = message;

      if (data.thread_id) {
        threadId = data.thread_id;
      }

      try {
        renderResult(data);

        if (data.budget_estimate) {
          renderBudgetCard(data.budget_estimate);
        }

        if (data.route_plan) {
          renderRouteMapCard(data.route_plan);
        }

        if (data.packing_list) {
          renderPackingCard(data.packing_list);
        }
      } catch (error) {
        console.error("renderResult failed:", error, data);
        renderError(error.message || String(error), "render");
      }

      scrollToEnd(true);
      setBusy(false);
      input.focus();
    }

    fetch(
      "/api/travel/stream",
      {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ message: message, thread_id: threadId })
      }
    )
      .then(function (response) {
        if (!response.ok || !response.body) {
          throw new Error("Request failed with HTTP " + response.status);
        }

        var reader = response.body.getReader();
        var decoder = new TextDecoder();
        var buffer = "";

        function pump() {
          return reader.read().then(function (result) {
            if (result.done) {
              if (!finished) {
                handleFailure(
                  "The connection ended before the plan finished.",
                  "network"
                );
              }

              return;
            }

            buffer += decoder.decode(result.value, { stream: true });

            var blocks = buffer.split("\n\n");
            buffer = blocks.pop();

            blocks.forEach(function (block) {
              if (!block.trim()) { return; }

              var eventMatch = block.match(/^event:\s*(.+)$/m);
              var dataMatch = block.match(/^data:\s*([\s\S]+)$/m);

              if (!dataMatch) { return; }

              var eventName = eventMatch ? eventMatch[1].trim() : "message";
              var payload;

              try {
                payload = JSON.parse(dataMatch[1]);
              } catch (e) {
                console.error("Could not parse SSE payload:", e, dataMatch[1]);
                return;
              }

              if (eventName === "step") {
                pipeline.markStep(payload.node);
              } else if (eventName === "done") {
                handleSuccess(payload);
              } else if (eventName === "error") {
                handleFailure(
                  payload.error || "The planner could not finish.",
                  payload.code === 428 ? "setup" : "server"
                );
              }
            });

            return pump();
          });
        }

        return pump();
      })
      .catch(function (error) {
        handleFailure(error.message || String(error), "network");
      });
  }


  /* ============================================================
     HERO SEARCH
     ============================================================ */

  heroSearch.addEventListener(
    "submit",
    function (event) {
      event.preventDefault();

      var value =
        heroInput.value.trim();

      if (!value) {
        heroInput.focus();

        toast(
          "Tell me where you want to go."
        );

        return;
      }


      /*
       * Put hero text into the main
       * conversation composer as well.
       */

      send(value);

      heroInput.value = "";
    }
  );


  heroInput.addEventListener(
    "keydown",
    function (event) {
      if (
        event.key === "Enter"
      ) {
        event.preventDefault();

        heroSearch.requestSubmit();
      }
    }
  );


  /* ============================================================
     NEW TRIP
     ============================================================ */

  function startNewTrip() {
    if (busy) {
      toast(
        "Wait for the current plan to finish."
      );

      return;
    }


    threadId = null;

    messages.innerHTML = "";


    /*
     * Reset hero input
     */

    heroInput.value = "";


    /*
     * Reset main composer
     */

    input.value = "";

    autosize();


    /*
     * Close builder
     */

    builder.hidden = true;

    builderToggle.classList.remove(
      "is-on"
    );


    /*
     * Reset builder fields
     */

    clearBuilder();


    updateEmptyState();


    if (isReady()) {
      input.focus();
    }
  }


  $("newTripBtn").addEventListener(
    "click",
    startNewTrip
  );


  /* ============================================================
     MAIN COMPOSER
     ============================================================ */

  function autosize() {
    input.style.height = "auto";

    var maxHeight = 200;
    var newHeight = Math.min(input.scrollHeight, maxHeight);

    input.style.height = newHeight + "px";

    /* Hide scrollbar when content fits.
      Show it only when the textarea reaches max height. */
    if (input.scrollHeight > maxHeight) {
      input.style.overflowY = "auto";
    } else {
      input.style.overflowY = "hidden";
    }
  }


  input.addEventListener(
    "input",
    autosize
  );


  input.addEventListener(
    "keydown",
    function (event) {
      if (
        event.key === "Enter" &&
        !event.shiftKey
      ) {
        event.preventDefault();

        send();
      }
    }
  );


  composer.addEventListener(
    "submit",
    function (event) {
      event.preventDefault();

      send();
    }
  );


  /* ============================================================
     TRIP BUILDER
     ============================================================ */

  builderToggle.addEventListener(
    "click",
    function () {
      var shouldShow =
        builder.hidden;

      builder.hidden =
        !shouldShow;

      builderToggle.classList.toggle(
        "is-on",
        shouldShow
      );

      if (shouldShow) {
        $("fFrom").focus();
      }
    }
  );


  /* ============================================================
     INTEREST CHIPS
     ============================================================ */

  document
    .querySelectorAll(
      "#interestChips .chip"
    )
    .forEach(function (chip) {
      chip.addEventListener(
        "click",
        function () {
          chip.classList.toggle(
            "on"
          );
        }
      );
    });


  /* ============================================================
     CLEAR BUILDER
     ============================================================ */

  function clearBuilder() {
    [
      "fFrom",
      "fTo",
      "fDate",
      "fDays",
      "fPeople",
      "fBudget"
    ].forEach(function (id) {
      var field = $(id);

      if (field) {
        field.value = "";
      }
    });


    document
      .querySelectorAll(
        "#interestChips .chip"
      )
      .forEach(function (chip) {
        chip.classList.remove(
          "on"
        );
      });
  }


  $("builderClear").addEventListener(
    "click",
    function () {
      clearBuilder();

      toast(
        "Trip builder cleared."
      );
    }
  );


  /* ============================================================
     APPLY TRIP BUILDER
     ============================================================ */

  $("builderApply").addEventListener(
    "click",
    function () {
      var from =
        $("fFrom").value.trim();

      var to =
        $("fTo").value.trim();

      var date =
        $("fDate").value;

      var days =
        $("fDays").value.trim();

      var people =
        $("fPeople").value.trim();

      var budget =
        $("fBudget").value.trim();


      var interests = [];


      document
        .querySelectorAll(
          "#interestChips .chip.on"
        )
        .forEach(function (chip) {
          interests.push(
            chip.getAttribute(
              "data-value"
            )
          );
        });


      if (!to) {
        toast(
          "Add a destination first."
        );

        $("fTo").focus();

        return;
      }


      var parts = [
        "Plan a"
      ];


      if (days) {
        parts.push(
          days +
            (
              days === "1"
                ? " day"
                : " day"
            )
        );
      }


      parts.push(
        "trip to " +
          to
      );


      if (from) {
        parts.push(
          "from " +
            from
        );
      }


      if (date) {
        var dateObject =
          new Date(
            date +
              "T00:00:00"
          );

        if (
          !isNaN(
            dateObject.getTime()
          )
        ) {
          parts.push(
            "departing " +
              dateObject.toLocaleDateString(
                undefined,
                {
                  day: "numeric",
                  month: "long",
                  year: "numeric"
                }
              )
          );
        }
      }


      if (people) {
        parts.push(
          "for " +
            people +
            (
              people === "1"
                ? " traveller"
                : " travellers"
            )
        );
      }


      if (budget) {
        parts.push(
          "with a budget of " +
            budget
        );
      }


      if (interests.length) {
        parts.push(
          "focused on " +
            interests.join(
              ", "
            )
        );
      }


      var sentence =
        parts.join(" ") +
        ". Find flights, hotels, the weather outlook and a day-by-day itinerary.";


      input.value =
        sentence;

      autosize();


      builder.hidden =
        true;

      builderToggle.classList.remove(
        "is-on"
      );


      input.focus();
    }
  );


  /* ============================================================
   POPULAR DESTINATIONS
   ============================================================ */

  function planTripFor(destination) {
    if (!destination) {
      return;
    }

    if (!isReady()) {
      toast("Add your API keys first.");
      openSettings();
      return;
    }

    send(
      "Plan a trip to " +
        destination +
        ". Find flights, hotels, the weather outlook and a day-by-day itinerary."
    );
  }

  document
    .querySelectorAll(
      ".destination-card"
    )
    .forEach(function (card) {
      card.setAttribute(
        "tabindex",
        "0"
      );

      card.setAttribute(
        "role",
        "button"
      );


      function chooseDestination() {
        planTripFor(card.getAttribute("data-destination"));
      }


      card.addEventListener(
        "click",
        chooseDestination
      );


      card.addEventListener(
        "keydown",
        function (event) {
          if (
            event.key === "Enter" ||
            event.key === " "
          ) {
            event.preventDefault();

            chooseDestination();
          }
        }
      );
    });


  /* ============================================================
     DESTINATIONS SEARCH OVERLAY
     ============================================================ */

  var destinationsOverlay = $("destinationsOverlay");
  var destinationsBack = $("destinationsBack");
  var destinationsSearchInput = $("destinationsSearchInput");
  var destinationsOverlayBody = $("destinationsOverlayBody");

  var destinationsSearchTimer = null;
  var destinationsSearchSeq = 0;

  function openDestinationsOverlay() {
    if (!destinationsOverlay) { return; }

    destinationsOverlay.hidden = false;
    destinationsSearchInput.value = "";
    loadPopularDestinations();

    setTimeout(function () {
      destinationsSearchInput.focus();
    }, 50);
  }

  function closeDestinationsOverlay() {
    if (destinationsOverlay) {
      destinationsOverlay.hidden = true;
    }
  }

  function destinationResultCard(place) {
    var card = createElement("article", "destination-card");
    card.setAttribute("tabindex", "0");
    card.setAttribute("role", "button");

    var imageWrap = createElement("div", "destination-image");

    if (place.image) {
      var img = document.createElement("img");
      img.src = place.image;
      img.alt = place.name;
      img.loading = "lazy";

      img.addEventListener("error", function () {
        card.classList.add("no-image");
        imageWrap.innerHTML = "";
        imageWrap.appendChild(
          createIcon("M20 10c0 5-8 12-8 12S4 15 4 10a8 8 0 1 1 16 0Z")
        );
      });

      imageWrap.appendChild(img);
    } else {
      card.classList.add("no-image");
      imageWrap.appendChild(
        createIcon("M20 10c0 5-8 12-8 12S4 15 4 10a8 8 0 1 1 16 0Z")
      );
    }

    card.appendChild(imageWrap);

    var info = createElement("div", "destination-info");
    info.appendChild(createElement("h3", null, place.name));
    info.appendChild(createElement("p", null, place.subtitle || place.display_name || ""));
    card.appendChild(info);

    function choose() {
      closeDestinationsOverlay();
      planTripFor(place.display_name || place.name);
    }

    card.addEventListener("click", choose);
    card.addEventListener("keydown", function (event) {
      if (event.key === "Enter" || event.key === " ") {
        event.preventDefault();
        choose();
      }
    });

    return card;
  }

  function renderDestinationResults(results, heading) {
    destinationsOverlayBody.innerHTML = "";

    if (!results.length) {
      destinationsOverlayBody.innerHTML =
        '<p class="destinations-empty">No places found. Try a different search.</p>';
      return;
    }

    if (heading) {
      destinationsOverlayBody.appendChild(
        createElement("h3", "destinations-heading", heading)
      );
    }

    var grid = createElement("div", "destinations-result-grid");

    results.forEach(function (place) {
      grid.appendChild(destinationResultCard(place));
    });

    destinationsOverlayBody.appendChild(grid);
  }

  function loadPopularDestinations() {
    destinationsOverlayBody.innerHTML =
      '<p class="destinations-loading">Loading popular destinations…</p>';

    fetch("/api/destinations/popular")
      .then(function (r) { return r.json(); })
      .then(function (data) {
        renderDestinationResults(data.results || [], "Popular Destinations");
      })
      .catch(function () {
        destinationsOverlayBody.innerHTML =
          '<p class="destinations-error">Could not load destinations.</p>';
      });
  }

  function runDestinationsSearch(query) {
    var seq = ++destinationsSearchSeq;

    destinationsOverlayBody.innerHTML =
      '<p class="destinations-loading">Searching…</p>';

    fetch("/api/destinations/search?q=" + encodeURIComponent(query))
      .then(function (r) { return r.json(); })
      .then(function (data) {
        if (seq !== destinationsSearchSeq) { return; }
        renderDestinationResults(data.results || [], null);
      })
      .catch(function () {
        if (seq !== destinationsSearchSeq) { return; }
        destinationsOverlayBody.innerHTML =
          '<p class="destinations-error">Could not reach the server. Try again.</p>';
      });
  }

  if (destinationsSearchInput) {
    destinationsSearchInput.addEventListener("input", function () {
      var query = destinationsSearchInput.value.trim();

      clearTimeout(destinationsSearchTimer);

      if (query.length < 2) {
        loadPopularDestinations();
        return;
      }

      // Debounced - the search hits a live, rate-limited geocoding
      // service under the hood, so we wait for a pause in typing
      // rather than searching on every keystroke.
      destinationsSearchTimer = setTimeout(function () {
        runDestinationsSearch(query);
      }, 600);
    });
  }

  if (destinationsBack) {
    destinationsBack.addEventListener("click", closeDestinationsOverlay);
  }

  document.addEventListener("keydown", function (event) {
    if (
      event.key === "Escape" &&
      destinationsOverlay &&
      !destinationsOverlay.hidden
    ) {
      closeDestinationsOverlay();
    }
  });


  /* ============================================================
     VIEW ALL DESTINATIONS
     ============================================================ */

  $("viewAllDestinations").addEventListener(
    "click",
    openDestinationsOverlay
  );


  /* ============================================================
     PAGE VISIBILITY
     ------------------------------------------------------------
     When the user returns to the tab,
     refresh API status.
     ============================================================ */

  document.addEventListener(
    "visibilitychange",
    function () {
      if (
        !document.hidden
      ) {
        refreshConfig();
      }
    }
  );


  /* ============================================================
     HEALTH CHECK
     ------------------------------------------------------------
     /api/config is the main configuration
     source. /health is checked as a fallback/
     connectivity indicator when available.
     ============================================================ */

  function checkHealth() {
    return fetch(
      "/health",
      {
        cache: "no-store"
      }
    )
      .then(function (response) {
        return response.ok;
      })
      .catch(function () {
        return false;
      });
  }


  /* ============================================================
     INITIALIZATION
     ============================================================ */

  initTheme();

  autosize();

  updateEmptyState();


  /*
   * Check configuration when page loads.
   */

  refreshConfig()
    .then(function () {
      if (isReady()) {
        input.focus();
      }
    });

  refreshCurrentUser();


  /*
   * Refresh configuration every minute.
   */

  setInterval(
    refreshConfig,
    60000
  );


  /*
   * Optional health check every
   * 60 seconds.
   */

  setInterval(
    function () {
      checkHealth();
    },
    60000
  );


})();
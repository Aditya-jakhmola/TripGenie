/* ============================================================
   TripGenie — Tiny Markdown Renderer
   ------------------------------------------------------------
   No external dependencies.

   Supports:
   - Headings
   - Bold / italic / bold-italic
   - Strikethrough
   - Inline code
   - Fenced code blocks
   - Links
   - Bare URLs
   - Bullet lists
   - Numbered lists
   - Nested lists
   - Blockquotes
   - Tables
   - Horizontal rules
   - Paragraphs

   IMPORTANT:
   All HTML is escaped before formatting so AI-generated
   content cannot directly inject arbitrary HTML.
   ============================================================ */

(function (global) {

  "use strict";


  /* ==========================================================
     HTML ESCAPING
     ========================================================== */

  function escapeHtml(value) {

    return String(value)

      .replace(/&/g, "&amp;")

      .replace(/</g, "&lt;")

      .replace(/>/g, "&gt;")

      .replace(/"/g, "&quot;")

      .replace(/'/g, "&#39;");
  }


  /* ==========================================================
     URL SAFETY
     ========================================================== */

  function isSafeUrl(url) {

    if (!url) return false;

    var value = String(url).trim();

    return /^(https?:\/\/|mailto:|\/|#)/i.test(value);
  }


  /* ==========================================================
     INLINE MARKDOWN
     ========================================================== */

  function formatRun(text) {

    var out = escapeHtml(text);


    /* --------------------------------------------------------
       Markdown links

       Example:
       [Google](https://google.com)
       -------------------------------------------------------- */

    out = out.replace(
      /\[([^\]]+)\]\(([^)\s]+)(?:\s+"[^"]*")?\)/g,
      function (match, label, url) {

        if (!isSafeUrl(url)) {
          return match;
        }

        return (
          '<a href="' +
          url +
          '" target="_blank" rel="noopener noreferrer">' +
          label +
          "</a>"
        );
      }
    );


    /* --------------------------------------------------------
       Bare URLs

       Example:
       https://example.com
       -------------------------------------------------------- */

    out = out.replace(
      /(^|[\s(])(https?:\/\/[^\s<)"']+[^\s<).,;:!?"'])/gi,
      function (match, prefix, url) {

        return (
          prefix +
          '<a href="' +
          url +
          '" target="_blank" rel="noopener noreferrer">' +
          url +
          "</a>"
        );
      }
    );


    /* --------------------------------------------------------
       Bold + italic

       ***text***
       ___text___
       -------------------------------------------------------- */

    out = out.replace(
      /\*\*\*([^*]+)\*\*\*/g,
      "<strong><em>$1</em></strong>"
    );

    out = out.replace(
      /___([^_]+)___/g,
      "<strong><em>$1</em></strong>"
    );


    /* --------------------------------------------------------
       Bold

       **text**
       __text__
       -------------------------------------------------------- */

    out = out.replace(
      /\*\*([^*]+)\*\*/g,
      "<strong>$1</strong>"
    );

    out = out.replace(
      /__([^_]+)__/g,
      "<strong>$1</strong>"
    );


    /* --------------------------------------------------------
       Strikethrough

       ~~text~~
       -------------------------------------------------------- */

    out = out.replace(
      /~~([^~]+)~~/g,
      "<del>$1</del>"
    );


    /* --------------------------------------------------------
       Italic

       *text*
       _text_
       -------------------------------------------------------- */

    out = out.replace(
      /(^|[^\*\w])\*([^\*\n]+)\*(?!\*)/g,
      "$1<em>$2</em>"
    );

    out = out.replace(
      /(^|[^\_\w])_([^\_\n]+)_(?!_)/g,
      "$1<em>$2</em>"
    );


    return out;
  }


  /* ==========================================================
     INLINE PARSER
     ----------------------------------------------------------
     Code spans are separated first so markdown formatting
     doesn't modify their contents.
     ========================================================== */

  function inline(text) {

    if (text === null || text === undefined) {
      return "";
    }

    var parts = String(text).split(/(`+[^`]+`+)/g);

    var output = "";


    for (var i = 0; i < parts.length; i++) {

      var part = parts[i];

      if (!part) {
        continue;
      }


      /* Inline code */

      if (
        part.charAt(0) === "`" &&
        part.charAt(part.length - 1) === "`"
      ) {

        var code = part.replace(/^`+|`+$/g, "");

        output += "<code>" + escapeHtml(code) + "</code>";

      } else {

        output += formatRun(part);
      }
    }


    return output;
  }


  /* ==========================================================
     LIST DETECTION
     ========================================================== */

  var BULLET = /^(\s*)([-*+])\s+(.+)$/;

  var ORDERED = /^(\s*)(\d+)[.)]\s+(.+)$/;


  /* ==========================================================
     TABLE SEPARATOR
     ========================================================== */

  var TABLE_SEPARATOR =
    /^\s*\|?\s*:?-{2,}:?\s*(\|\s*:?-{2,}:?\s*)+\|?\s*$/;


  /* ==========================================================
     TABLE ROW
     ========================================================== */

  function splitTableRow(line) {

    var trimmed = line.trim();


    if (trimmed.charAt(0) === "|") {
      trimmed = trimmed.substring(1);
    }


    if (trimmed.charAt(trimmed.length - 1) === "|") {
      trimmed = trimmed.substring(
        0,
        trimmed.length - 1
      );
    }


    return trimmed
      .split("|")
      .map(function (cell) {
        return cell.trim();
      });
  }


  /* ==========================================================
     LIST PARSER
     ========================================================== */

  function parseList(lines, start) {

    var stack = [];

    var parts = [];

    var i = start;


    function closeDeeperThan(indent) {

      while (
        stack.length &&
        stack[stack.length - 1].indent > indent
      ) {

        var current = stack.pop();

        parts.push(
          "</li></" +
          current.tag +
          ">"
        );
      }
    }


    while (i < lines.length) {

      var line = lines[i];

      var match = line.match(BULLET);

      var tag = "ul";


      if (!match) {

        match = line.match(ORDERED);

        tag = "ol";
      }


      /* ------------------------------------------------------
         Not a list item
         ------------------------------------------------------ */

      if (!match) {

        /*
         * Allow indented continuation text.
         */

        if (
          stack.length &&
          line.trim() &&
          /^\s{2,}/.test(line)
        ) {

          parts.push(
            " " +
            inline(line.trim())
          );

          i++;

          continue;
        }


        break;
      }


      var indent = match[1]
        .replace(/\t/g, "    ")
        .length;


      /* ------------------------------------------------------
         First list
         ------------------------------------------------------ */

      if (!stack.length) {

        stack.push({
          tag: tag,
          indent: indent
        });

        parts.push(
          "<" +
          tag +
          "><li>"
        );

      }


      /* ------------------------------------------------------
         Nested list
         ------------------------------------------------------ */

      else if (
        indent >
        stack[stack.length - 1].indent
      ) {

        stack.push({
          tag: tag,
          indent: indent
        });

        parts.push(
          "<" +
          tag +
          "><li>"
        );

      }


      /* ------------------------------------------------------
         Same / shallower level
         ------------------------------------------------------ */

      else {

        closeDeeperThan(indent);


        if (!stack.length) {

          stack.push({
            tag: tag,
            indent: indent
          });

          parts.push(
            "<" +
            tag +
            "><li>"
          );

        }


        /* List type changed */

        else if (
          stack[stack.length - 1].tag !== tag
        ) {

          var old = stack.pop();

          parts.push(
            "</li></" +
            old.tag +
            ">"
          );

          stack.push({
            tag: tag,
            indent: indent
          });

          parts.push(
            "<" +
            tag +
            "><li>"
          );

        }


        /* Same list */

        else {

          parts.push(
            "</li><li>"
          );
        }
      }


      parts.push(
        inline(match[3])
      );


      i++;
    }


    /* Close all open lists */

    while (stack.length) {

      var current = stack.pop();

      parts.push(
        "</li></" +
        current.tag +
        ">"
      );
    }


    return {
      html: parts.join(""),
      next: i
    };
  }


  /* ==========================================================
     BLOCK PARSER
     ========================================================== */

  function render(source) {

    if (
      source === null ||
      source === undefined
    ) {
      return "";
    }


    var lines = String(source)
      .replace(/\r\n?/g, "\n")
      .split("\n");


    var html = [];

    var paragraph = [];

    var i = 0;


    /* --------------------------------------------------------
       Flush paragraph
       -------------------------------------------------------- */

    function flushParagraph() {

      if (!paragraph.length) {
        return;
      }


      html.push(
        "<p>" +
        inline(
          paragraph.join(" ")
        ) +
        "</p>"
      );


      paragraph = [];
    }


    /* ========================================================
       MAIN LOOP
       ======================================================== */

    while (i < lines.length) {

      var line = lines[i];


      /* ======================================================
         FENCED CODE BLOCK
         ====================================================== */

      var fence = line.match(
        /^\s*(```|~~~)\s*(.*)$/
      );


      if (fence) {

        flushParagraph();


        var marker = fence[1];

        var language = fence[2]
          ? fence[2].trim()
          : "";


        var codeLines = [];

        i++;


        while (
          i < lines.length &&
          lines[i].trim().indexOf(marker) !== 0
        ) {

          codeLines.push(
            lines[i]
          );

          i++;
        }


        /* Skip closing fence */

        if (i < lines.length) {
          i++;
        }


        var codeClass =
          language
            ? ' class="language-' +
              escapeHtml(language) +
              '"'
            : "";


        html.push(
          "<pre><code" +
          codeClass +
          ">" +
          escapeHtml(
            codeLines.join("\n")
          ) +
          "</code></pre>"
        );


        continue;
      }


      /* ======================================================
         BLANK LINE
         ====================================================== */

      if (!line.trim()) {

        flushParagraph();

        i++;

        continue;
      }


      /* ======================================================
         HORIZONTAL RULE
         ====================================================== */

      if (
        /^\s*([-*_])(?:\s*\1){2,}\s*$/.test(line)
      ) {

        flushParagraph();

        html.push("<hr />");

        i++;

        continue;
      }


      /* ======================================================
         HEADINGS
         ====================================================== */

      var heading = line.match(
        /^\s*(#{1,6})\s+(.+?)\s*#*\s*$/
      );


      if (heading) {

        flushParagraph();


        /*
         * Keep the UI clean by limiting very large headings.
         */

        var level = Math.min(
          heading[1].length,
          4
        );


        html.push(
          "<h" +
          level +
          ">" +
          inline(heading[2]) +
          "</h" +
          level +
          ">"
        );


        i++;

        continue;
      }


      /* ======================================================
         TABLE
         ====================================================== */

      if (
        line.indexOf("|") !== -1 &&
        i + 1 < lines.length &&
        TABLE_SEPARATOR.test(lines[i + 1])
      ) {

        flushParagraph();


        var header = splitTableRow(line);

        i += 2;


        var rows = [];


        while (
          i < lines.length &&
          lines[i].trim() &&
          lines[i].indexOf("|") !== -1
        ) {

          rows.push(
            splitTableRow(lines[i])
          );

          i++;
        }


        var table = [];


        table.push(
          '<div class="md-table-wrap">'
        );


        table.push("<table>");


        /* Header */

        table.push(
          "<thead><tr>"
        );


        header.forEach(
          function (cell) {

            table.push(
              "<th>" +
              inline(cell) +
              "</th>"
            );
          }
        );


        table.push(
          "</tr></thead>"
        );


        /* Body */

        table.push(
          "<tbody>"
        );


        rows.forEach(
          function (row) {

            table.push(
              "<tr>"
            );


            for (
              var c = 0;
              c < header.length;
              c++
            ) {

              table.push(
                "<td>" +
                inline(
                  row[c] || ""
                ) +
                "</td>"
              );
            }


            table.push(
              "</tr>"
            );
          }
        );


        table.push(
          "</tbody></table></div>"
        );


        html.push(
          table.join("")
        );


        continue;
      }


      /* ======================================================
         BLOCKQUOTE
         ====================================================== */

      if (
        /^\s*>\s?/.test(line)
      ) {

        flushParagraph();


        var quote = [];


        while (
          i < lines.length &&
          /^\s*>\s?/.test(lines[i])
        ) {

          quote.push(
            lines[i].replace(
              /^\s*>\s?/,
              ""
            )
          );

          i++;
        }


        html.push(
          "<blockquote>" +
          render(
            quote.join("\n")
          ) +
          "</blockquote>"
        );


        continue;
      }


      /* ======================================================
         LISTS
         ====================================================== */

      if (
        BULLET.test(line) ||
        ORDERED.test(line)
      ) {

        flushParagraph();


        var list = parseList(
          lines,
          i
        );


        html.push(
          list.html
        );


        i = list.next;

        continue;
      }


      /* ======================================================
         INDENTED CODE BLOCK
         ====================================================== */

      if (
        /^\s{4,}\S/.test(line)
      ) {

        flushParagraph();


        var indentedCode = [];


        while (
          i < lines.length &&
          (
            /^\s{4,}/.test(lines[i]) ||
            !lines[i].trim()
          )
        ) {

          if (!lines[i].trim()) {

            indentedCode.push("");

          } else {

            indentedCode.push(
              lines[i].replace(
                /^\s{4}/,
                ""
              )
            );
          }

          i++;
        }


        html.push(
          "<pre><code>" +
          escapeHtml(
            indentedCode.join("\n")
          ) +
          "</code></pre>"
        );


        continue;
      }


      /* ======================================================
         NORMAL PARAGRAPH TEXT
         ====================================================== */

      paragraph.push(
        line.trim()
      );


      i++;
    }


    /* Flush final paragraph */

    flushParagraph();


    return html.join("\n");
  }


  /* ==========================================================
     PUBLIC API
     ----------------------------------------------------------
     Your app.js uses:

         window.MD.render(text)

     So expose exactly that interface.
     ========================================================== */

  global.MD = {

    render: render,

    escape: escapeHtml

  };


})(window);
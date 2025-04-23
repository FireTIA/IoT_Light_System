window.addEventListener("DOMContentLoaded", () => {
    let capsLock = false;
    let keyboardVisible = true;
    let activeInput = null;
  
    const keyboardLayout = [
      ['1','2','3','4','5','6','7','8','9','0'],
      ['q','w','e','r','t','y','u','i','o','p'],
      ['a','s','d','f','g','h','j','k','l'],
      ['z','x','c','v','b','n','m'],
      ['caps', 'backspace', 'enter']
    ];
  
    const keyboard = document.createElement("div");
    keyboard.classList.add("vk-keyboard", "hidden");
  
    keyboardLayout.forEach(row => {
      const rowDiv = document.createElement("div");
      rowDiv.classList.add("vk-row");
  
      row.forEach(key => {
        const keyButton = document.createElement("div");
        keyButton.classList.add("vk-key");
        keyButton.dataset.action = key;
  
        keyButton.textContent =
          key === "backspace" ? "⌫" :
          key === "enter" ? "⏎" :
          key === "caps" ? "Caps" : key;
  
        keyButton.addEventListener("mousedown", e => {
          e.preventDefault(); // Не терять фокус
  
          if (!activeInput) return;
  
          const cursorPos = activeInput.selectionStart;
          const text = activeInput.value;
  
          if (key === "backspace") {
            if (cursorPos > 0) {
              activeInput.value =
                text.slice(0, cursorPos - 1) + text.slice(cursorPos);
              activeInput.setSelectionRange(cursorPos - 1, cursorPos - 1);
            }
          } else if (key === "enter") {
            if (activeInput.tagName.toLowerCase() === "textarea") {
              activeInput.value =
                text.slice(0, cursorPos) + "\n" + text.slice(cursorPos);
              activeInput.setSelectionRange(cursorPos + 1, cursorPos + 1);
            } else {
              activeInput.form?.submit();
            }
          } else if (key === "caps") {
            capsLock = !capsLock;
            document.querySelectorAll(".vk-key").forEach(btn => {
              const action = btn.dataset.action;
              if (action && action.length === 1 && /[a-z]/i.test(action)) {
                btn.textContent = capsLock
                  ? action.toUpperCase()
                  : action.toLowerCase();
              }
            });
            keyButton.classList.toggle("active");
          } else {
            const char = capsLock ? key.toUpperCase() : key;
            activeInput.value =
              text.slice(0, cursorPos) + char + text.slice(cursorPos);
            activeInput.setSelectionRange(cursorPos + 1, cursorPos + 1);
          }
        });
  
        rowDiv.appendChild(keyButton);
      });
  
      keyboard.appendChild(rowDiv);
    });
  
    document.body.appendChild(keyboard);
  
    // Кнопка сворачивания
    const toggleBtn = document.createElement("div");
    toggleBtn.classList.add("vk-toggle");
    toggleBtn.textContent = "🧩";
    toggleBtn.title = "Показать/скрыть клавиатуру";
  
    toggleBtn.addEventListener("click", () => {
      keyboard.classList.toggle("hidden");
      keyboardVisible = !keyboardVisible;
    });
  
    document.body.appendChild(toggleBtn);
  
    // Слежение за фокусом
    document.addEventListener("focusin", e => {
      const el = e.target;
      if (
        el.tagName.toLowerCase() === "input" ||
        el.tagName.toLowerCase() === "textarea"
      ) {
        activeInput = el;
      }
    });
  
    document.addEventListener("focusout", e => {
      // Оставляем activeInput при кликах по клавиатуре
      if (!e.relatedTarget || !e.relatedTarget.classList.contains("vk-key")) {
        activeInput = null;
      }
    });
  });
  
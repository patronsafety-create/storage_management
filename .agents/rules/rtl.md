# Mandatory RTL Display Policy for Persian Output

Whenever responding to the user in Persian:
1. Wrap all Persian text and reports in:
   `<div dir="rtl" style="direction: rtl; text-align: right; font-family: Tahoma, 'Vazirmatn', sans-serif;">`
   `...`
   `</div>`
2. Ensure markdown tables, lists, and numbers are rendered with right-to-left layout so punctuation, parentheses, and mixed English route names do not invert or become unreadable.
3. This applies permanently across all conversations and subagent tasks.

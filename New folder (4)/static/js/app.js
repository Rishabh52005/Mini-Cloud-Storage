document.addEventListener("click", async (event) => {
    const button = event.target.closest(".copy-button");
    if (!button) {
        return;
    }

    const originalLabel = button.textContent;
    const text = button.dataset.copyText;

    try {
        await navigator.clipboard.writeText(text);
        button.textContent = "Copied";
    } catch (error) {
        button.textContent = "Copy failed";
    }

    window.setTimeout(() => {
        button.textContent = originalLabel;
    }, 1600);
});

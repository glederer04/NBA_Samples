"use strict";

document.addEventListener(
    "error",
    function handleHeadshotError(event) {
        const image = event.target;

        if (
            !(image instanceof HTMLImageElement) ||
            (!image.classList.contains("player-headshot-image") &&
                !image.classList.contains("team-logo")) ||
            image.dataset.fallbackApplied === "true"
        ) {
            return;
        }

        image.dataset.fallbackApplied = "true";
        image.classList.add("is-placeholder");
        image.src = image.classList.contains("team-logo")
            ? "/assets/team-placeholder.svg"
            : "/assets/player-placeholder.svg";
    },
    true
);
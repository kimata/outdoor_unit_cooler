export const valueText = (value, digits=1) => {
    if (value == null) {
        return "?";
    } else {
        return value.toFixed(digits);
    }
};

export const dateText = (date) => {
    if (date == null) {
        return "?";
    } else {
        return date.format("M/D HH:mm:ss");
    }
};

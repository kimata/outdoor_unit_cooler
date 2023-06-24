export const valueText = (value) => {
    if (value == null) {
        return "?";
    } else {
        return value.toFixed(1);
    }
};

export const dateText = (date) => {
    if (date == null) {
        return "?";
    } else {
        return date.format("MM-DD HH:mm:ss");
    }
};

function get_checked_values(class_name) {
    var e = document.getElementsByClassName(class_name); var r = []; var c = 0;
    for (var i = 0; i < e.length; i++) {
        if (e[i].checked) { r[c] = e[i].value; c++;}
    }
    return r;
}
function switch_checked(class_name, check) {
    var js_check = (check.toLowerCase() == 'true');
    var e = document.getElementsByClassName(class_name);
    for (var i = 0; i < e.length; i++) {
        e[i].checked = js_check;
    }
}

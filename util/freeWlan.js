let wpa = require ('./wpa.js');

wpa.unmanageUnusedInterfaces()
.then((interfaces) => {
    interfaces.forEach((interface) => {
        console.log(interface + ' no longer managed.');
    });
});
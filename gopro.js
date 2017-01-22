let fs = require('fs');
let request = require('request');

function setupGPIO(gpio){
    if (fs.existsSync('/sys/class/gpio/gpio' + gpio ) == false) {
        fs.writeFileSync('/sys/class/gpio/export', gpio);
    }
    fs.writeFileSync('/sys/class/gpio/gpio' + gpio + '/direction', 'in');
    let pollRate = 100;
    let cooldown = 3000;
    let cooldownTimer = 0;

    setInterval(() => {
        if (cooldownTimer <= 0){
            if (readGPIO(gpio) == '1'){
                console.log('Snap!');
                cooldownTimer = cooldown;
                takePicture();
            }
        } else {
            cooldownTimer -= pollRate;
        }
    }, pollRate);
}

function readGPIO(gpio){
    return fs.readFileSync('/sys/class/gpio/gpio' + gpio + '/value', 'utf8')[0];
}

function takePicture(){
    request.get('http://192.168.1.254/?custom=1&cmd=3001?par=1')
    .on('response', (response => {
        request.get('http://192.168.1.254/?custom=1&cmd=1001')
        .on('response', (response => {
            request.get('http://192.168.1.254/?custom=1&cmd=3001?par=0')
            .on('error', (err => {
                console.log('Take Picture Failed');
            }))
        }))
        .on('error', (err => {
            console.log('Take Picture Failed');
        }))
    }))
    .on('error', (err => {
        console.log('Take Picture Failed');
    }))
}

module.exports = {
    setupGPIO: setupGPIO,
    takePicture: takePicture
};

// The entire "database" for this demo lives right here.
// Every transaction that comes in gets pushed to this array.
// Restarting the server wipes everything — that's intentional for a demo API.
const transactions = [];

module.exports = { transactions };

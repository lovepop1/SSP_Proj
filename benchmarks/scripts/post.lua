-- wrk POST request script
-- We use a 10KB payload equivalent to match the 'payload_gen'

wrk.method = "POST"
wrk.headers["Content-Type"] = "application/json"

-- We pad the string to guarantee processing the 10KB threshold inside the server
local padding = string.rep("X", 10000)
wrk.body = '{"transaction_id":"12345","timestamp":1.0,"user_id":1000,"amount":10.5,"currency":"USD","description":"test","merchant_code":"M123","metadata":"' .. padding .. '"}'

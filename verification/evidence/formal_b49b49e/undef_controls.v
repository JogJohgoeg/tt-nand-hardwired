module masked(input s, a, output good, bad);
wire branch = s ? 1'bx : a;
assign good = a; assign bad = s ? a : branch; endmodule
module leaking(input s, a, output good, bad);
assign good = a; assign bad = s ? 1'bx : a; endmodule

// SPDX-License-Identifier: MIT
// Tiny Tapeout top for the H2 first-silicon candidate: #279 hard logic + DOT32_T.
// Serial protocol (clk = serial bit clock, MSB-first data):
//   ui_in[0] DIN   ui_in[1] CS_n(0=active)   ui_in[2] SHIFT   ui_in[3] core(0=#279,1=DOT32_T)   ui_in[4] RUN
//   LOAD : for k in n_in-1..0: DIN=bit[k], SHIFT=1 for one clk.
//   RUN  : RUN=1 for one clk -> latches the selected core's outputs into the output shift register.
//   READ : sample DOUT before each of n_out SHIFT clocks; response active then clears.
// Synchronous active-low reset wins over ena/CS_n. RUN wins over SHIFT and
// replaces an unread response. CS_n=1 or ena=0 holds every register.
`default_nettype none
module tt_um_jogjohgoeg_hardwired(
    input  wire [7:0] ui_in,
    output wire [7:0] uo_out,
    input  wire [7:0] uio_in,
    output wire [7:0] uio_out,
    output wire [7:0] uio_oe,
    input  wire       ena,
    input  wire       clk,
    input  wire       rst_n
);
    reg  [319:0] in_sr;
    reg  [31:0]  out_sr;
    reg  [5:0]   out_count;
    wire busy = (out_count != 6'd0);

    wire shift = ena && !ui_in[1] && ui_in[2];
    wire run   = ena && !ui_in[1] && ui_in[4];

    wire [1:0]  out279;
    wire [31:0] out32;
    cell_279 c279(.din(in_sr[14:0]), .dout(out279));
    dot32_t  d32 (.din(in_sr),       .dout(out32));

    always @(posedge clk) begin
        if (!rst_n) begin
            in_sr <= 320'd0;
            out_sr <= 32'd0;
            out_count <= 6'd0;
        end else if (ena) begin
            if (ui_in[1]) begin
                // CS_n high: idle, hold state
            end else if (run) begin
                out_sr <= ui_in[3] ? out32 : {out279, 30'd0};
                out_count <= ui_in[3] ? 6'd32 : 6'd2;
            end else if (shift) begin
                if (busy) begin
                    out_sr <= {out_sr[30:0], 1'b0};
                    out_count <= out_count - 6'd1;
                end else begin
                    in_sr <= {in_sr[318:0], ui_in[0]};
                end
            end
        end
    end

    assign uo_out[0] = busy ? out_sr[31] : 1'b0;
    assign uo_out[1] = busy;
    assign uo_out[2] = ui_in[3];
    assign uo_out[7:3] = 5'd0;

    assign uio_out = 8'd0;
    assign uio_oe  = 8'h00;

    wire unused = &{1'b0, uio_in, ui_in[7:5]};
endmodule
`default_nettype wire

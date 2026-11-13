// nco -- 32-bit phase accumulator with sine and cosine outputs.
//
// `sync` clears the phase, so every shot of an experiment starts the carrier
// at the same point and shots can be added coherently.  The phase itself is
// exported one cycle ahead of the sine/cosine it produces (the table is a
// synchronous ROM), which is what the transmitter's square-wave drive uses.
module nco (
    input  wire               clk,
    input  wire               sync,
    input  wire        [31:0] freq,     // f_out = freq * f_clk / 2^32
    output reg         [31:0] phase,
    output wire signed [11:0] sin,
    output wire signed [11:0] cos
);
    // Read into unsigned registers: a signed one keeps the table out of
    // block RAM (KarpelesLab/reticle#12).
    reg [11:0] sin_q, cos_q;
    assign sin = $signed(sin_q);
    assign cos = $signed(cos_q);

    reg [11:0] rom [0:1023];
    initial $readmemh("sine1024.hex", rom);

    wire [9:0] a_sin = phase[31:22];
    wire [9:0] a_cos = phase[31:22] + 10'd256;

    always @(posedge clk) begin
        if (sync) phase <= 32'd0;
        else      phase <= phase + freq;
        sin_q <= rom[a_sin];
        cos_q <= rom[a_cos];
    end

    // Without a defined start the mixer feeds unknowns into integrators
    // that are never cleared.
    initial begin
        phase = 32'd0; sin_q = 12'd0; cos_q = 12'd0;
    end
endmodule

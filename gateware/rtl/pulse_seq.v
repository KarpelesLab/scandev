// pulse_seq -- runs a table of timed steps, `nshots` times over.
//
// A step is {ctrl[7:0], dur[31:0]}: hold `ctrl` on the outputs for `dur`
// clock cycles (at least 2), then go on.  The step with CTRL_LAST ends the
// shot.  Steps follow each other with no gap; between two shots the outputs
// are idle (all zero) for exactly two cycles.
//
//   ctrl[0]    tx_en     transmitter drives the probe
//   ctrl[2:1]  tx_quad   transmit phase in quarter turns (0, 90, 180, 270)
//   ctrl[3]    blank     receiver input shorted / LNA protected
//   ctrl[4]    qdamp     damping switch across the tank closed
//   ctrl[5]    acquire   capture down-converted samples
//   ctrl[6]    sync      on the first cycle of the step, restart the carrier
//                        phase and the decimator
//   ctrl[7]    last      this is the final step of the shot
module pulse_seq (
    input  wire        clk,
    input  wire        rst,

    input  wire        prog_we,
    input  wire  [5:0] prog_addr,
    input  wire [39:0] prog_data,

    input  wire        start,
    input  wire [15:0] nshots,
    output reg         busy,
    output reg  [15:0] shot,        // shots completed
    output reg         shot_start,  // one cycle, before each shot's first step

    output wire        tx_en,
    output wire  [1:0] tx_quad,
    output wire        blank,
    output wire        qdamp,
    output wire        acquire,
    output reg         sync
);
    reg [39:0] prog [0:63];
    reg [39:0] step_q;
    reg  [5:0] pc;

    always @(posedge clk) begin
        if (prog_we) prog[prog_addr] <= prog_data;
        step_q <= prog[pc];
    end

    localparam S_IDLE = 2'd0, S_PRIME = 2'd1, S_LOAD = 2'd2, S_RUN = 2'd3;
    reg  [1:0] state;
    reg  [7:0] ctrl;
    reg [31:0] cnt;

    wire running = (state == S_RUN);
    assign tx_en   = running & ctrl[0];
    assign tx_quad = ctrl[2:1];
    assign blank   = running & ctrl[3];
    assign qdamp   = running & ctrl[4];
    assign acquire = running & ctrl[5];

    always @(posedge clk) begin
        sync       <= 1'b0;
        shot_start <= 1'b0;
        if (rst) begin
            state <= S_IDLE;
            busy  <= 1'b0;
            shot  <= 16'd0;
            pc    <= 6'd0;
        end else case (state)
            S_IDLE: if (start) begin
                busy  <= 1'b1;
                shot  <= 16'd0;
                pc    <= 6'd0;
                state <= S_PRIME;
            end
            S_PRIME: begin
                shot_start <= 1'b1;
                state      <= S_LOAD;
            end
            S_LOAD: begin
                ctrl  <= step_q[39:32];
                cnt   <= step_q[31:0];
                sync  <= step_q[38];
                pc    <= pc + 6'd1;
                state <= S_RUN;
            end
            S_RUN: if (cnt == 32'd1) begin
                if (ctrl[7]) begin
                    shot <= shot + 16'd1;
                    pc   <= 6'd0;
                    if (shot + 16'd1 == nshots) begin
                        busy  <= 1'b0;
                        state <= S_IDLE;
                    end else
                        state <= S_PRIME;
                end else begin
                    ctrl <= step_q[39:32];
                    cnt  <= step_q[31:0];
                    sync <= step_q[38];
                    pc   <= pc + 6'd1;
                end
            end else
                cnt <= cnt - 32'd1;
        endcase
    end

    initial begin
        state = S_IDLE; busy = 0; shot = 0; pc = 0; ctrl = 0; cnt = 0;
        sync = 0; shot_start = 0; step_q = 0;
    end
endmodule

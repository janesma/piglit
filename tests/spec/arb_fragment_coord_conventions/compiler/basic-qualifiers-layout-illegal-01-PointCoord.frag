/* [config]
 * expect_result: fail
 * glsl_version: 1.10
 * require_extensions: GL_ARB_fragment_coord_conventions
 * check_link: false
 * [end config]
 */

/*
 * Section 4.3.x.1 (Input Layout Qualifiers) of the
 * ARB_fragment_coord_conventions spec says:
 *
 *     "Fragment shaders can have an input layout only for redeclaring the
 *     built-in variable gl_FragCoord (see section 7.2). The layout qualifier
 *     identifiers for gl_FragCoord are
 *
 *         <layout-qualifier-id>
 *             origin_upper_left
 *             pixel_center_integer"
 *
 * Test should fail because input layout should only apply to gl_FragCoord.
 */

#version 110

#extension GL_ARB_fragment_coord_conventions : require

layout(origin_upper_left, pixel_center_integer) in vec2 gl_PointCoord;

void main()
{
     gl_FragColor = gl_FragCoord.xyzz;
}

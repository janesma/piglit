#include "piglit-util-gl-common.h"

PIGLIT_GL_TEST_CONFIG_BEGIN

	config.supports_gl_compat_version = 11;
	config.supports_gl_core_version = 31;

	config.window_visual = PIGLIT_GL_VISUAL_RGBA | PIGLIT_GL_VISUAL_DOUBLE;

PIGLIT_GL_TEST_CONFIG_END

#define TEXTURE_WIDTH 32
#define TEXTURE_HEIGHT 32

enum { NOSTAGE, VS, FS } stage = NOSTAGE;
enum { NONE = -1, RED, GREEN, BLUE, ALPHA, ZERO, ONE } swizzle = NONE;
enum { UNORM, FLOAT, INT, UINT, NUM_COMPTYPES } comptype = UNORM;
enum { SAMPLER_2D, SAMPLER_2DARRAY, SAMPLER_CUBE, SAMPLER_CUBEARRAY } sampler = SAMPLER_2D;
bool use_offset = false;
bool use_nonconst = false;
int components = 0;
int comp_select = -1;

GLenum internalformat_for_components[][4] = {
	{ GL_R16, GL_RG16, GL_RGB16, GL_RGBA16, },
	{ GL_R32F, GL_RG32F, GL_RGB32F, GL_RGBA32F, },
	{ GL_R16I, GL_RG16I, GL_RGB16I, GL_RGBA16I },
	{ GL_R16UI, GL_RG16UI, GL_RGB16UI, GL_RGBA16UI },
};
GLenum format_for_components[][4] = {
	{ GL_RED, GL_RG, GL_RGB, GL_RGBA },
	{ GL_RED, GL_RG, GL_RGB, GL_RGBA },
	{ GL_RED_INTEGER, GL_RG_INTEGER, GL_RGB_INTEGER,  GL_RGBA_INTEGER },
	{ GL_RED_INTEGER, GL_RG_INTEGER, GL_RGB_INTEGER,  GL_RGBA_INTEGER },
};
GLenum swizzles[] = { GL_RED, GL_GREEN, GL_BLUE, GL_ALPHA, GL_ZERO, GL_ONE };
int slices_for_sampler[] = { 1, 3, 6, 12 };
GLenum target_for_sampler[] = { GL_TEXTURE_2D, GL_TEXTURE_2D_ARRAY, GL_TEXTURE_CUBE_MAP, GL_TEXTURE_CUBE_MAP_ARRAY };

unsigned char *pixels;
float *expected;

enum piglit_result
piglit_display(void)
{
	int i, j;
	bool pass = true;

	glViewport(0, 0, TEXTURE_WIDTH, TEXTURE_HEIGHT);
	glClearColor(0.4, 0.4, 0.4, 0.4);
	glClear(GL_COLOR_BUFFER_BIT);

	if (swizzle >= 0) {
		GLint sw[] = { GL_ZERO, GL_ZERO, GL_ZERO, GL_ZERO };
		if (comp_select != -1)
			sw[comp_select] = swizzles[swizzle];
		else
			sw[0] = swizzles[swizzle];
		glTexParameteriv(target_for_sampler[sampler], GL_TEXTURE_SWIZZLE_RGBA, sw);
	}

	if (stage == FS)
		glDrawArrays(GL_TRIANGLES, 0, 6);
	else
		glDrawArrays(GL_POINTS, 0, TEXTURE_WIDTH * TEXTURE_HEIGHT);

	for (j = 1; j < TEXTURE_HEIGHT - 1; j++)
		for (i = 1; i < TEXTURE_WIDTH - 1; i++) {
			float *pe = &expected[4 * (j * TEXTURE_WIDTH + i)];
			pass = piglit_probe_pixel_rgba(i, j, pe) && pass;
		}

	piglit_present_results();

	return pass ? PIGLIT_PASS : PIGLIT_FAIL;
}

/* TODO:
 * Test other sampler types: gsampler2D|gsampler2DArray|gsamplerCube|gsamplerCubeArray
 * Test GS texturing too -- Paul?
 */

static unsigned char
pixel_value(int i, int j)
{
	if (swizzle == ZERO)
		return 0;
	if (swizzle == ONE)
		return 255;

	if (use_offset) {
		/* apply texel offset */
		i += TEXTURE_WIDTH + -8;
		j += TEXTURE_HEIGHT + 7;
	}

	/* WRAP at border */
	i %= TEXTURE_WIDTH;
	j %= TEXTURE_HEIGHT;

	return i + j * TEXTURE_WIDTH;
}

static float
norm_value(int x)
{
	return (float)x / 255.0f;
}

static void
make_image(int num_channels, int use_channel)
{
	unsigned char *pp = pixels;
	int i, j, ch;

	for (j = 0; j < TEXTURE_HEIGHT; j++)
		for (i = 0; i < TEXTURE_WIDTH; i++)
			for (ch = 0; ch < num_channels; ch++)
				*pp++ = (ch == use_channel) ? (i+j*TEXTURE_WIDTH) : 128;
}

static void
make_expected(void)
{
	float *pe = expected;
	int i, j;

	for (j = 0; j < TEXTURE_HEIGHT; j++)
		for (i = 0; i < TEXTURE_WIDTH; i++) {
			*pe++ = norm_value(pixel_value(i, j + 1));
			*pe++ = norm_value(pixel_value(i + 1, j + 1));
			*pe++ = norm_value(pixel_value(i + 1, j));
			*pe++ = norm_value(pixel_value(i, j));
		}
}

static void
upload_verts(void)
{
	if (stage == VS) {
		float v[4 * TEXTURE_WIDTH * TEXTURE_HEIGHT], *pv = v;
		int i, j;
		for (j = 0; j < TEXTURE_HEIGHT; j++)
			for (i = 0; i < TEXTURE_WIDTH; i++) {
				*pv++ = (i + 0.5f) * 2 / TEXTURE_WIDTH - 1;
				*pv++ = (j + 0.5f) * 2 / TEXTURE_HEIGHT - 1;
				*pv++ = 0;
				*pv++ = 1;
			}
		glBufferData(GL_ARRAY_BUFFER, sizeof(v), v, GL_STATIC_DRAW);
	}
	else {
		static const float verts[] = {
			-1, -1, 0, 1,
			-1, 1, 0, 1,
			1, 1, 0, 1,
			-1, -1, 0, 1,
			1, 1, 0, 1,
			1, -1, 0, 1,
		};
		glBufferData(GL_ARRAY_BUFFER, sizeof(verts), verts, GL_STATIC_DRAW);
	}
}

void
do_requires(void)
{
	int max_components;
	piglit_require_GLSL_version(130);
	piglit_require_extension("GL_ARB_texture_gather");

	/* check whether component count will actually work */
	glGetIntegerv(GL_MAX_PROGRAM_TEXTURE_GATHER_COMPONENTS_ARB, &max_components);
	if (components > max_components) {
		printf("Test requires gather from texture with %d components;"
		       "This implementation only supports %d\n",
		       components, max_components);
		piglit_report_result(PIGLIT_SKIP);
	}

	/* if we are trying to swizzle, check that we can! */
	if (swizzle != -1)
		piglit_require_extension("GL_EXT_texture_swizzle");

	/* check the sampler type we want actually exists */
	if (sampler == SAMPLER_CUBEARRAY)
		piglit_require_extension("GL_ARB_texture_cube_map_array");

	if (use_offset && (sampler == SAMPLER_CUBE || sampler == SAMPLER_CUBEARRAY)) {
		printf("Offset is not supported with cube or cube array samplers.\n");
		piglit_report_result(PIGLIT_SKIP);
	}

	/* if we are trying to specify the component from the shader,
	 * or use non-constant offsets, check that we have ARB_gpu_shader5
	 */
	if (comp_select != -1 || use_nonconst)
		piglit_require_extension("GL_ARB_gpu_shader5");
}

static void
upload_2d(GLenum target, void *pixels)
{
	glTexImage2D(target, 0,
		     internalformat_for_components[comptype][components - 1],
		     TEXTURE_WIDTH, TEXTURE_HEIGHT,
		     0, format_for_components[comptype][components-1],
		     GL_UNSIGNED_BYTE, pixels);
}

static void
upload_array_slice(GLenum target, int slice, void *pixels)
{
	glTexSubImage3D(target, 0, 0, 0, slice, TEXTURE_WIDTH, TEXTURE_HEIGHT, 1,
			format_for_components[comptype][components-1],
			GL_UNSIGNED_BYTE, pixels);
}

static void
upload_3d(GLenum target, void *pixels)
{
	glTexImage3D(target, 0,
		     internalformat_for_components[comptype][components - 1],
		     TEXTURE_WIDTH, TEXTURE_HEIGHT,
		     slices_for_sampler[sampler], 0,
		     format_for_components[comptype][components-1],
		     GL_UNSIGNED_BYTE, pixels);
}

static int
channel_to_fill(void) {
	if (swizzle != NONE)
		return swizzle;
	if (comp_select != NONE)
		return comp_select;
	return 0;
}

static void
do_texture_setup(void)
{
	GLuint tex;
	GLenum target = target_for_sampler[sampler];
	pixels = malloc(components * sizeof(unsigned char) * TEXTURE_WIDTH * TEXTURE_HEIGHT);
	expected = malloc(4 * sizeof(float) * TEXTURE_WIDTH * TEXTURE_HEIGHT);

	glGenTextures(1, &tex);
	glBindTexture(target, tex);

	make_image(components, channel_to_fill());
	make_expected();

	switch(sampler) {
	case SAMPLER_2D:
		upload_2d(target, pixels);
		break;
	case SAMPLER_2DARRAY:
		upload_3d(target, NULL);
		upload_array_slice(target, 1, pixels);
		break;
	case SAMPLER_CUBE:
		/* legacy cubes are weird. the only sane way to specify the whole
		 * thing at once is using glTexStorage, and we'd rather not rely on
		 * ARB_texture_storage just for that. */
		upload_2d(GL_TEXTURE_CUBE_MAP_NEGATIVE_X, NULL);
		upload_2d(GL_TEXTURE_CUBE_MAP_POSITIVE_X, NULL);
		upload_2d(GL_TEXTURE_CUBE_MAP_NEGATIVE_Y, NULL);
		upload_2d(GL_TEXTURE_CUBE_MAP_POSITIVE_Y, NULL);
		upload_2d(GL_TEXTURE_CUBE_MAP_NEGATIVE_Z, NULL);
		upload_2d(GL_TEXTURE_CUBE_MAP_POSITIVE_Z, pixels);
		break;
	case SAMPLER_CUBEARRAY:
		upload_3d(target, NULL);
		upload_array_slice(target, 10, pixels);
		break;
	}

	glTexParameteri(target, GL_TEXTURE_MIN_FILTER, GL_NEAREST);
	glTexParameteri(target, GL_TEXTURE_MAG_FILTER, GL_NEAREST);
}

static void
do_shader_setup(void)
{
	GLint prog;
	GLint sampler_loc, offset_loc;
	char *vs_code, *fs_code;
	char *prefix[] = { "" /* unorm */, "" /* float */, "i" /* int */, "u" /* uint */ };
	char *scale[] = {
		"vec4(1)",		/* unorm + GL_ONE swizzle */
		"vec4(1)",		/* float */
		"vec4(1.0/255.0)",	/* int */
		"vec4(1.0/255.0)",	/* uint */
	};
	char *samplersuffix[] = { "2D", "2DArray", "Cube", "CubeArray" };
	char *vs_tc_expr[] = {
		"0.5 * pos.xy + vec2(0.5)",
		"vec3(0.5 * pos.xy + vec2(0.5), 1)",
		"vec3(pos.x, -pos.y, 1)",		/* cube */
		"vec4(pos.x, -pos.y, 1, 1)"		/* cube array */
	};
	char *fs_tc_expr[] = {
		"gl_FragCoord.xy / textureSize(s, 0).xy",
		"vec3(gl_FragCoord.xy / textureSize(s, 0).xy, 1)",
		"vec3(vec2(2, -2) * (gl_FragCoord.xy / textureSize(s, 0).xy - vec2(0.5)), 1)",	/* cube */
		"vec4(vec2(2, -2) * (gl_FragCoord.xy / textureSize(s, 0).xy - vec2(0.5)), 1, 1)"	/* cube array */
	};
	char *comp_expr[] = {"", ", 0", ", 1", ", 2", ", 3"};
	bool need_shader5 = (comp_select != -1) || use_nonconst;

	if (stage == VS) {
		asprintf(&vs_code, "#version 130\n"
				"#extension GL_ARB_explicit_attrib_location: require\n"
				"#extension GL_ARB_texture_gather: require\n"
				"%s"
				"%s"
				"\n"
				"layout(location=0) in vec4 pos;\n"
				"uniform %ssampler%s s;\n"
				"%s"
				"out vec4 c;\n"
				"\n"
				"void main() {\n"
				"	gl_Position = pos;\n"
				"	c = %s * textureGather%s(s, %s %s %s);\n"
				"}\n",
				sampler == SAMPLER_CUBEARRAY ? "#extension GL_ARB_texture_cube_map_array: require\n" : "",
				need_shader5 ? "#extension GL_ARB_gpu_shader5: require\n" : "",
				prefix[comptype],
				samplersuffix[sampler],
				use_nonconst ? "uniform ivec2 o1,o2;\n" : "",
				swizzle == ONE ? scale[0] : scale[comptype],
				use_offset ? "Offset" : "",
				vs_tc_expr[sampler],
				use_nonconst ? ", o1+o2" : use_offset ? ", ivec2(-8,7)" :  "",
				comp_expr[1 + comp_select]);
		asprintf(&fs_code,
				"#version 130\n"
				"\n"
				"in vec4 c;\n"
				"\n"
				"void main() {\n"
				"	gl_FragColor = c;\n"
				"}\n");
	}
	else {
		asprintf(&vs_code,
				"#version 130\n"
				"#extension GL_ARB_explicit_attrib_location: require\n"
				"layout(location=0) in vec4 pos;\n"
				"\n"
				"void main() {\n"
				"	gl_Position = pos;\n"
				"}\n");
		asprintf(&fs_code,
				"#version 130\n"
				"#extension GL_ARB_texture_gather: require\n"
				"%s"
				"%s"
				"\n"
				"uniform %ssampler%s s;\n"
				"%s"
				"\n"
				"void main() {\n"
				"	gl_FragColor = %s * textureGather%s(s, %s %s %s);\n"
				"}\n",
				sampler == SAMPLER_CUBEARRAY ? "#extension GL_ARB_texture_cube_map_array: require\n" : "",
				need_shader5 ? "#extension GL_ARB_gpu_shader5: require\n" : "",
				prefix[comptype],
				samplersuffix[sampler],
				use_nonconst ? "uniform ivec2 o1,o2;\n" : "",
				swizzle == ONE ? scale[0] : scale[comptype],
				use_offset ? "Offset" : "",
				fs_tc_expr[sampler],
				use_nonconst ? ", o1+o2" : use_offset ? ", ivec2(-8,7)" :  "",
				comp_expr[1 + comp_select]);
	}

	prog = piglit_build_simple_program(vs_code, fs_code);

	glUseProgram(prog);
	sampler_loc = glGetUniformLocation(prog, "s");
	glUniform1i(sampler_loc, 0);

	if (use_nonconst) {
		offset_loc = glGetUniformLocation(prog, "o1");
		glUniform2i(offset_loc, -8, 0);
		offset_loc = glGetUniformLocation(prog, "o2");
		glUniform2i(offset_loc, 0, 7);
	}
}

static void
do_geometry_setup(void)
{
	GLuint vbo;
	if (piglit_get_gl_version() >= 31) {
		GLuint vao;
		glGenVertexArrays(1, &vao);
		glBindVertexArray(vao);
	}

	glGenBuffers(1, &vbo);
	glBindBuffer(GL_ARRAY_BUFFER, vbo);
	upload_verts();
	glVertexAttribPointer(0, 4, GL_FLOAT, GL_FALSE, 0, 0);
	glEnableVertexAttribArray(0);
}

void
fail_with_usage(void)
{
	printf("Usage: textureGather <stage> [offset] [nonconst] <components> <swizzle> <comptype> <sampler> <compselect>\n"
	       "	stage = vs|fs\n"
	       "	components = r|rg|rgb|rgba\n"
	       "	swizzle = red|green|blue|alpha|zero|one\n"
	       "	comptype = unorm|float|uint|int\n"
	       "	sampler = 2D|2DArray|Cube|CubeArray\n"
	       "	compselect = 0|1|2|3");
	piglit_report_result(PIGLIT_SKIP);
}

void
piglit_init(int argc, char **argv)
{
	int i;
	for (i = 1; i < argc; i++) {
		char *opt = argv[i];
		if (!strcmp(opt, "vs")) stage = VS;
		else if (!strcmp(opt, "fs")) stage = FS;
		else if (!strcmp(opt, "offset")) use_offset = true;
		else if (!strcmp(opt, "nonconst")) use_nonconst = true;
		else if (!strcmp(opt, "r")) components = 1;
		else if (!strcmp(opt, "rg")) components = 2;
		else if (!strcmp(opt, "rgb")) components = 3;
		else if (!strcmp(opt, "rgba")) components = 4;
		else if (!strcmp(opt, "red")) swizzle = 0;
		else if (!strcmp(opt, "green")) swizzle = 1;
		else if (!strcmp(opt, "blue")) swizzle = 2;
		else if (!strcmp(opt, "alpha")) swizzle = 3;
		else if (!strcmp(opt, "zero")) swizzle = 4;
		else if (!strcmp(opt, "one")) swizzle = 5;
		else if (!strcmp(opt, "unorm")) comptype = UNORM;
		else if (!strcmp(opt, "float")) comptype = FLOAT;
		else if (!strcmp(opt, "int")) comptype = INT;
		else if (!strcmp(opt, "uint")) comptype = UINT;
		else if (!strcmp(opt, "2D")) sampler = SAMPLER_2D;
		else if (!strcmp(opt, "2DArray")) sampler = SAMPLER_2DARRAY;
		else if (!strcmp(opt, "Cube")) sampler = SAMPLER_CUBE;
		else if (!strcmp(opt, "CubeArray")) sampler = SAMPLER_CUBEARRAY;
		else if (!strcmp(opt, "0")) comp_select = 0;
		else if (!strcmp(opt, "1")) comp_select = 1;
		else if (!strcmp(opt, "2")) comp_select = 2;
		else if (!strcmp(opt, "3")) comp_select = 3;
	}

	if (stage == NOSTAGE) fail_with_usage();
	if (components == 0) fail_with_usage();

	if (use_nonconst) use_offset = true;

	do_requires();
	do_texture_setup();
	do_shader_setup();
	do_geometry_setup();

	if (!piglit_check_gl_error(GL_NO_ERROR)) {
		printf("Error in init\n");
		piglit_report_result(PIGLIT_FAIL);
	}
}
